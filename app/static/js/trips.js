(function () {
  const { api, h, renderList, showLoadError, bindForm, toast, formatDate } = window.Tripzy;
  const list = document.getElementById("trip-list");
  const form = document.getElementById("trip-form");
  const groupSelect = document.getElementById("trip-group");
  const choices = document.getElementById("trip-member-choices");
  let groups = [];

  function dateRange(t) {
    if (t.start_date && t.end_date) return `${formatDate(t.start_date)} – ${formatDate(t.end_date)}`;
    if (t.start_date) return `From ${formatDate(t.start_date)}`;
    return "Dates not set";
  }

  async function loadTrips() {
    try {
      const trips = await api("/api/trips");
      renderList(list, trips, (t) =>
        h("li", {},
          h("div", { class: "grow" },
            h("a", { class: "title", href: `/trips/${t.id}` }, t.name), " ",
            t.is_owner ? h("span", { class: "badge badge-owner" }, "Owner") : null,
            h("div", { class: "sub" }, `${t.destination} · ${dateRange(t)} · ${t.member_count} member${t.member_count === 1 ? "" : "s"}`)),
          h("a", { class: "btn btn-small", href: `/trips/${t.id}` }, "Open")),
        "No trips yet. Create your first one.");
    } catch (err) { showLoadError(list, err); }
  }

  async function loadFriends() {
    try {
      const [friends, groupList] = await Promise.all([api("/api/friends"), api("/api/friend-groups")]);
      groups = groupList;
      groupSelect.append(...groups.map((g) => h("option", { value: g.id }, `${g.name} (${g.members.length})`)));
      if (friends.length) {
        choices.replaceChildren(...friends.map((f) =>
          h("label", {}, h("input", { type: "checkbox", name: "member_ids", value: f.id }), `${f.display_name} (${f.email})`)));
      }
    } catch { /* member preselection is optional */ }
  }

  groupSelect.addEventListener("change", () => {
    const group = groups.find((g) => String(g.id) === groupSelect.value);
    const ids = new Set(group ? group.members.map((m) => String(m.id)) : []);
    choices.querySelectorAll('input[name="member_ids"]').forEach((box) => { box.checked = ids.has(box.value); });
    if (group) toast(`Preselected ${ids.size} friend${ids.size === 1 ? "" : "s"} from ${group.name}. Review before creating.`);
  });

  bindForm(form, async (values, f) => {
    const memberIds = [...f.querySelectorAll('input[name="member_ids"]:checked')].map((b) => Number(b.value));
    const trip = await api("/api/trips", {
      method: "POST",
      body: {
        name: values.name,
        destination: values.destination,
        description: values.description || null,
        start_date: values.start_date || null,
        end_date: values.end_date || null,
        member_ids: memberIds,
      },
    });
    toast("Trip created");
    location.href = `/trips/${trip.id}`;
  });

  loadTrips();
  loadFriends();
})();
