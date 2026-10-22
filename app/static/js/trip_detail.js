(function () {
  const { api, h, renderList, showLoadError, action, bindForm, toast, formatDate, rupees, safeHref } = window.Tripzy;
  const { id: tripId, isOwner } = window.TRIP;
  const base = `/api/trips/${tripId}`;
  const memberList = document.getElementById("member-list");
  let trip = null;

  function dateText(t) {
    if (t.start_date && t.end_date) return `${formatDate(t.start_date)} – ${formatDate(t.end_date)}`;
    if (t.start_date) return `From ${formatDate(t.start_date)}`;
    if (t.end_date) return `Until ${formatDate(t.end_date)}`;
    return "Not set";
  }

  function renderDetails() {
    document.getElementById("trip-title").textContent = trip.name;
    document.getElementById("trip-subtitle").textContent = trip.destination;
    const rows = [
      ["Destination", trip.destination],
      ["Dates", dateText(trip)],
      ["Description", trip.description || "—"],
      ["Owner", trip.owner.display_name],
      ["Created", formatDate(trip.created_at)],
    ];
    document.getElementById("trip-details").replaceChildren(...rows.flatMap(([k, v]) => [h("dt", {}, k), h("dd", {}, v)]));
    const form = document.getElementById("edit-trip-form");
    if (form) {
      form.name.value = trip.name;
      form.destination.value = trip.destination;
      form.description.value = trip.description || "";
      form.start_date.value = trip.start_date || "";
      form.end_date.value = trip.end_date || "";
    }
  }

  function renderMembers() {
    renderList(memberList, trip.members, (m) =>
      h("li", {},
        h("div", { class: "grow" },
          h("span", { class: "title" }, m.display_name), " ",
          m.role === "owner" ? h("span", { class: "badge badge-owner" }, "Owner") : null,
          h("div", { class: "sub" }, m.email)),
        isOwner && m.role !== "owner"
          ? h("button", { class: "btn btn-small", type: "button", onclick: (e) =>
              action(e.currentTarget, async () => { await api(`${base}/members/${m.id}`, { method: "DELETE" }); await load(); },
                { confirm: `Remove ${m.display_name} from ${trip.name}?`, success: `${m.display_name} removed from the trip` }) }, "Remove member")
          : null),
      "No members.");
  }

  async function loadFriendOptions() {
    const select = document.getElementById("member-friend");
    if (!select) return;
    try {
      const friends = await api("/api/friends");
      const memberIds = new Set(trip.members.map((m) => m.id));
      const options = friends.filter((f) => !memberIds.has(f.id)).map((f) => h("option", { value: f.id }, `${f.display_name} (${f.email})`));
      select.replaceChildren(h("option", { value: "" }, options.length ? "— Choose a friend —" : "No friends left to add"), ...options);
    } catch { /* optional */ }
  }

  async function loadBalances() {
    const el = document.getElementById("balance-summary");
    try {
      const data = await api(`${base}/balances`);
      renderList(el, data.balances, (b) =>
        h("li", {},
          h("span", { class: "grow" }, b.display_name),
          h("span", { class: b.net_minor > 0 ? "pos" : b.net_minor < 0 ? "neg" : "muted" },
            b.net_minor > 0 ? `gets back ${rupees(b.net)}` : b.net_minor < 0 ? `owes ${rupees(-b.net)}` : "settled")),
        "No members.");
    } catch (err) { showLoadError(el, err); }
  }

  async function loadSaved() {
    const el = document.getElementById("saved-summary");
    try {
      const places = await api(`${base}/locations`);
      renderList(el, places, (p) => {
        const href = safeHref(p.provider_url);
        return h("li", {},
          h("div", { class: "grow" },
            href ? h("a", { class: "title", href, target: "_blank", rel: "noopener noreferrer" }, p.name) : h("span", { class: "title" }, p.name),
            h("div", { class: "sub" }, [p.category, p.address].filter(Boolean).join(" · "))));
      }, "No saved places yet.");
    } catch (err) { showLoadError(el, err); }
  }

  async function load() {
    try {
      trip = await api(base);
    } catch (err) {
      showLoadError(memberList, err);
      return;
    }
    renderDetails();
    renderMembers();
    loadFriendOptions();
    loadBalances();
  }

  bindForm(document.getElementById("edit-trip-form"), async (values) => {
    trip = await api(base, {
      method: "PATCH",
      body: {
        name: values.name,
        destination: values.destination,
        description: values.description || null,
        start_date: values.start_date || null,
        end_date: values.end_date || null,
      },
    });
    renderDetails();
    toast("Trip updated");
  });

  bindForm(document.getElementById("add-member-form"), async (values, form) => {
    const body = values.user_id ? { user_id: Number(values.user_id) } : { email: (values.email || "").trim() };
    if (!body.user_id && !body.email) throw new Tripzy.ApiError("Choose a friend or enter an email address", 422, "VALIDATION_ERROR", "user_id");
    const member = await api(`${base}/members`, { method: "POST", body });
    form.reset();
    toast(`${member.display_name} added to the trip`);
    await load();
  });

  document.getElementById("delete-trip-btn")?.addEventListener("click", (e) =>
    action(e.currentTarget, async () => {
      await api(base, { method: "DELETE" });
      location.href = "/trips";
    }, { confirm: `Delete "${trip ? trip.name : "this trip"}"? Its members, expenses and saved locations will be permanently removed.` }));

  load();
  loadSaved();
})();
