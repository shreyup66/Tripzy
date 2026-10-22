(function () {
  const { api, h, renderList, showLoadError, action, bindForm, toast, formatDate, rupees, toPaise, paiseToString } = window.Tripzy;
  const base = `/api/trips/${window.TRIP.id}`;
  const form = document.getElementById("expense-form");
  const payerSelect = document.getElementById("exp-payer");
  const participantsEl = document.getElementById("participants");
  const statusEl = document.getElementById("split-status");
  const amountInput = document.getElementById("exp-amount");
  let members = [];

  const method = () => form.querySelector('input[name="split_method"]:checked').value;
  const rows = () => [...participantsEl.querySelectorAll(".participant")];
  const selectedRows = () => rows().filter((r) => r.querySelector('input[type="checkbox"]').checked);

  function renderParticipants() {
    payerSelect.replaceChildren(...members.map((m) =>
      h("option", { value: m.id, selected: m.id === window.TRIPZY.userId }, m.display_name)));
    participantsEl.replaceChildren(...members.map((m) =>
      h("div", { class: "participant", dataset: { userId: m.id } },
        h("label", {}, h("input", { type: "checkbox", checked: true, "aria-label": `Include ${m.display_name}` }), m.display_name),
        h("input", { type: "text", inputmode: "decimal", placeholder: "0.00", "aria-label": `Share for ${m.display_name}`, autocomplete: "off" }))));
    updateMode();
  }

  function updateMode() {
    const custom = method() === "custom";
    for (const row of rows()) {
      const checked = row.querySelector('input[type="checkbox"]').checked;
      const share = row.querySelector('input[type="text"]');
      share.hidden = !custom;
      share.disabled = !checked;
    }
    updateStatus();
  }

  /* Live preview; the server recomputes and validates everything. */
  function updateStatus() {
    const total = toPaise(amountInput.value);
    const selected = selectedRows();
    statusEl.className = "split-status";
    if (!selected.length) {
      statusEl.textContent = "Select at least one participant.";
      statusEl.classList.add("bad");
      return;
    }
    if (total === null || total <= 0) {
      statusEl.textContent = amountInput.value.trim() ? "Enter a valid amount" : "Enter an amount to see the split.";
      if (amountInput.value.trim()) statusEl.classList.add("bad");
      return;
    }
    if (method() === "equal") {
      const n = selected.length;
      const each = Math.floor(total / n);
      const remainder = total % n;
      statusEl.textContent = remainder
        ? `${n} people · ${rupees(paiseToString(each))}–${rupees(paiseToString(each + 1))} each. ${rupees(paiseToString(total))} doesn't divide evenly, so ${remainder} ${remainder === 1 ? "person pays" : "people pay"} ₹0.01 more.`
        : `${n} ${n === 1 ? "person" : "people"} · ${rupees(paiseToString(each))} each`;
      statusEl.classList.add("ok");
      return;
    }
    let sum = 0;
    for (const row of selected) {
      const value = row.querySelector('input[type="text"]').value;
      const paise = value.trim() === "" ? 0 : toPaise(value);
      if (paise === null || paise < 0) {
        statusEl.textContent = "Enter a valid amount for each share.";
        statusEl.classList.add("bad");
        return;
      }
      sum += paise;
    }
    const diff = total - sum;
    if (diff === 0) {
      statusEl.textContent = `Shares total ${rupees(paiseToString(sum))} of ${rupees(paiseToString(total))} — matches the expense amount.`;
      statusEl.classList.add("ok");
    } else {
      statusEl.textContent = `Shares total ${rupees(paiseToString(sum))} of ${rupees(paiseToString(total))} — ${rupees(paiseToString(Math.abs(diff)))} ${diff > 0 ? "left to assign" : "too much"}.`;
      statusEl.classList.add("bad");
    }
  }

  form.addEventListener("input", updateStatus);
  form.addEventListener("change", (e) => {
    if (e.target.name === "split_method" || e.target.type === "checkbox") updateMode();
  });
  document.getElementById("select-all").addEventListener("click", () => {
    rows().forEach((r) => { r.querySelector('input[type="checkbox"]').checked = true; });
    updateMode();
  });
  document.getElementById("select-none").addEventListener("click", () => {
    rows().forEach((r) => { r.querySelector('input[type="checkbox"]').checked = false; });
    updateMode();
  });

  bindForm(form, async (values) => {
    const selected = selectedRows();
    const body = {
      description: values.description,
      amount: values.amount,
      currency: "INR",
      payer_id: Number(values.payer_id),
      split_method: method(),
    };
    if (body.split_method === "equal") {
      body.participant_ids = selected.map((r) => Number(r.dataset.userId));
    } else {
      body.shares = selected.map((r) => ({
        user_id: Number(r.dataset.userId),
        amount: r.querySelector('input[type="text"]').value.trim() || "0",
      }));
    }
    await api(`${base}/expenses`, { method: "POST", body });
    form.description.value = "";
    form.amount.value = "";
    rows().forEach((r) => { r.querySelector('input[type="text"]').value = ""; });
    updateStatus();
    toast("Expense added");
    refresh();
  });

  function expenseItem(e) {
    return h("li", {},
      h("div", { class: "grow" },
        h("div", { class: "title" }, e.description),
        h("div", { class: "sub" }, `Paid by ${e.payer.display_name} · ${formatDate(e.created_at)} · ${e.split_method === "equal" ? "Split equally" : "Custom shares"}`),
        h("div", { class: "shares" }, e.shares.map((s) => `${s.display_name} ${rupees(s.amount)}`).join(" · ")),
        e.rounding_note ? h("div", { class: "shares" }, e.rounding_note) : null),
      h("span", { class: "amount" }, rupees(e.amount)),
      h("button", { class: "btn btn-small", type: "button", onclick: (ev) =>
        action(ev.currentTarget, async () => { await api(`${base}/expenses/${e.id}`, { method: "DELETE" }); refresh(); },
          { confirm: `Delete "${e.description}" (${rupees(e.amount)})? Balances will be recalculated.`, success: "Expense deleted" }) }, "Delete"));
  }

  async function loadExpenses() {
    const el = document.getElementById("expense-list");
    try {
      renderList(el, await api(`${base}/expenses`), expenseItem, "No expenses yet. Add the first one above.");
    } catch (err) { showLoadError(el, err); }
  }

  async function loadBalances() {
    const el = document.getElementById("balances");
    const settleEl = document.getElementById("settlements");
    try {
      const data = await api(`${base}/balances`);
      el.removeAttribute("aria-busy");
      el.replaceChildren(h("div", { class: "table-wrap" }, h("table", {},
        h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Member"), h("th", { scope: "col", class: "num" }, "Paid"),
          h("th", { scope: "col", class: "num" }, "Share"), h("th", { scope: "col", class: "num" }, "Net"))),
        h("tbody", {}, data.balances.map((b) => h("tr", { dataset: { userId: b.user_id } },
          h("th", { scope: "row" }, b.display_name),
          h("td", { class: "num" }, rupees(b.paid)),
          h("td", { class: "num" }, rupees(b.owed)),
          h("td", { class: `num ${b.net_minor > 0 ? "pos" : b.net_minor < 0 ? "neg" : ""}` },
            b.net_minor > 0 ? `+${rupees(b.net)}` : b.net_minor < 0 ? `−${rupees(-b.net)}` : rupees(0))))))),
        h("p", { class: "hint" }, "Net = paid − share. Positive means they should get money back."));
      renderList(settleEl, data.settlements, (s) =>
        h("li", {}, h("span", { class: "grow" }, h("strong", {}, s.from_name), " pays ", h("strong", {}, s.to_name)), h("span", { class: "amount" }, rupees(s.amount))),
        "Everyone is settled up.");
    } catch (err) { showLoadError(el, err); }
  }

  function refresh() {
    loadExpenses();
    loadBalances();
  }

  (async () => {
    try {
      const trip = await api(base);
      members = trip.members;
      renderParticipants();
    } catch (err) { toast(err.message, "error"); }
    refresh();
  })();
})();
