/* Shared helpers: API calls with CSRF, safe DOM building, forms, toasts. */
(function () {
  "use strict";

  class ApiError extends Error {
    constructor(message, status, code, field, errors) {
      super(message);
      this.status = status;
      this.code = code;
      this.field = field;
      this.errors = errors || [];
    }
  }

  function csrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : "";
  }

  function setCsrfToken(token) {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && token) meta.content = token;
  }

  async function api(path, { method = "GET", body } = {}) {
    const headers = { Accept: "application/json" };
    if (method !== "GET") headers["X-CSRF-Token"] = csrfToken();
    const options = { method, headers, credentials: "same-origin" };
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    let response;
    try {
      response = await fetch(path, options);
    } catch {
      throw new ApiError("Network error. Check your connection and try again.", 0, "NETWORK_ERROR");
    }
    if (response.status === 204) return null;
    let data = null;
    try { data = await response.json(); } catch { /* non-JSON body */ }
    if (!response.ok) {
      if (response.status === 401 && !["/login", "/signup"].includes(location.pathname)) {
        location.href = "/login?next=" + encodeURIComponent(location.pathname);
      }
      const detail = data && typeof data.detail === "string" ? data.detail : `Request failed (${response.status})`;
      throw new ApiError(detail, response.status, data && data.code, data && data.field, data && data.errors);
    }
    return data;
  }

  /* h("li", {class: "x", onclick: fn}, "text", childNode) — strings become text nodes, never HTML. */
  function h(tag, attrs, ...children) {
    const el = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs || {})) {
      if (value === null || value === undefined || value === false) continue;
      if (key.startsWith("on") && typeof value === "function") el.addEventListener(key.slice(2), value);
      else if (key === "class") el.className = value;
      else if (key === "dataset") Object.assign(el.dataset, value);
      else if (value === true) el.setAttribute(key, "");
      else el.setAttribute(key, String(value));
    }
    for (const child of children.flat()) {
      if (child === null || child === undefined || child === false) continue;
      el.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return el;
  }

  function toast(message, type = "success") {
    const box = document.getElementById("toasts");
    if (!box) return;
    const el = h("div", { class: type === "error" ? "toast toast-error" : "toast" }, message);
    box.append(el);
    setTimeout(() => el.remove(), 4500);
  }

  function renderList(listEl, items, renderItem, emptyText) {
    listEl.replaceChildren();
    listEl.removeAttribute("aria-busy");
    if (!items.length) {
      listEl.append(h("li", { class: "empty" }, emptyText));
      return;
    }
    for (const item of items) listEl.append(renderItem(item));
  }

  function showLoadError(container, err) {
    container.removeAttribute("aria-busy");
    const tag = container.tagName === "UL" ? "li" : "p";
    container.replaceChildren(h(tag, { class: "empty" }, err.message || "Couldn't load this section."));
  }

  function clearErrors(form) {
    const box = form.querySelector(".form-error");
    if (box) { box.hidden = true; box.textContent = ""; }
    form.querySelectorAll(".field-error").forEach((e) => e.remove());
    form.querySelectorAll("[aria-invalid]").forEach((e) => e.removeAttribute("aria-invalid"));
  }

  function showErrors(form, err) {
    const fieldErrors = err.errors && err.errors.length ? err.errors : err.field ? [{ field: err.field, message: err.message }] : [];
    let placed = false;
    for (const fe of fieldErrors) {
      const name = (fe.field || "").split(".")[0];
      const input = name && form.querySelector(`[name="${CSS.escape(name)}"]`);
      if (!input || input.type === "radio" || input.type === "checkbox") continue;
      const id = `${input.id || name}-error`;
      if (document.getElementById(id)) continue;
      input.setAttribute("aria-invalid", "true");
      input.setAttribute("aria-describedby", id);
      input.closest(".field")?.append(h("p", { class: "field-error", id }, fe.message));
      placed = true;
    }
    const box = form.querySelector(".form-error");
    if (box) {
      box.textContent = err.message;
      box.hidden = false;
    } else if (!placed) {
      toast(err.message, "error");
    }
    form.querySelector('[aria-invalid="true"]')?.focus();
  }

  /* Run fn while a button is disabled, so double-clicks can't submit twice. */
  async function busy(button, fn) {
    if (button && button.disabled) return;
    if (button) { button.disabled = true; button.setAttribute("aria-busy", "true"); }
    try {
      return await fn();
    } finally {
      if (button) { button.disabled = false; button.removeAttribute("aria-busy"); }
    }
  }

  /* Wire a form: handler(values, form) may throw ApiError; input is preserved on error. */
  function bindForm(form, handler) {
    if (!form) return;
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const submit = form.querySelector('[type="submit"]');
      busy(submit, async () => {
        clearErrors(form);
        try {
          await handler(Object.fromEntries(new FormData(form)), form);
        } catch (err) {
          if (err instanceof ApiError) showErrors(form, err);
          else { console.error(err); toast("Something went wrong.", "error"); }
        }
      });
    });
  }

  /* Button action with confirmation and feedback. */
  function action(button, fn, { confirm: question, success } = {}) {
    return busy(button, async () => {
      if (question && !window.confirm(question)) return;
      try {
        await fn();
        if (success) toast(success);
      } catch (err) {
        toast(err.message || "Something went wrong.", "error");
      }
    });
  }

  function formatDate(iso) {
    if (!iso) return "";
    const date = iso.length === 10 ? new Date(iso + "T00:00:00") : new Date(iso + (iso.endsWith("Z") ? "" : "Z"));
    return date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
  }

  function rupees(amount) {
    const n = Number(amount);
    return "₹" + n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  /* Client-side mirror of the server's paise parsing (server always revalidates). */
  function toPaise(text) {
    const s = String(text ?? "").trim();
    if (!/^-?(\d+(\.\d{0,2})?|\.\d{1,2})$/.test(s)) return null;
    const negative = s.startsWith("-");
    const [whole, frac = ""] = s.replace("-", "").split(".");
    const paise = Number(whole || "0") * 100 + Number((frac + "00").slice(0, 2));
    return negative ? -paise : paise;
  }

  function paiseToString(paise) {
    const sign = paise < 0 ? "-" : "";
    const abs = Math.abs(paise);
    return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}`;
  }

  function safeHref(url) {
    try {
      const u = new URL(url);
      return u.protocol === "http:" || u.protocol === "https:" ? u.href : null;
    } catch {
      return null;
    }
  }

  document.getElementById("logout-btn")?.addEventListener("click", (e) =>
    busy(e.currentTarget, async () => {
      try { await api("/api/auth/logout", { method: "POST" }); } catch { /* already signed out */ }
      location.href = "/login";
    })
  );

  window.Tripzy = {
    ApiError, api, h, toast, renderList, showLoadError, bindForm, busy, action, clearErrors, showErrors,
    formatDate, rupees, toPaise, paiseToString, safeHref, setCsrfToken,
  };
})();
