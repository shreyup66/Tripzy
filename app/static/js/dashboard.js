(function () {
  const { api, h, renderList, showLoadError, action, formatDate } = window.Tripzy;
  const tripList = document.getElementById("dash-trip-list");
  const requestList = document.getElementById("dash-request-list");

  async function loadTrips() {
    try {
      const trips = await api("/api/trips");
      renderList(tripList, trips.slice(0, 5), (t) =>
        h("li", {},
          h("div", { class: "grow" },
            h("a", { class: "title", href: `/trips/${t.id}` }, t.name),
            h("div", { class: "sub" }, t.destination, t.start_date ? ` · ${formatDate(t.start_date)}` : "", ` · ${t.member_count} member${t.member_count === 1 ? "" : "s"}`)),
          h("a", { class: "btn btn-small", href: `/trips/${t.id}/budget` }, "Budget")),
        "No trips yet. Create one to get started.");
    } catch (err) { showLoadError(tripList, err); }
  }

  async function loadRequests() {
    try {
      const requests = await api("/api/friend-requests?direction=incoming");
      renderList(requestList, requests, (r) =>
        h("li", {},
          h("div", { class: "grow" }, h("div", { class: "title" }, r.requester.display_name), h("div", { class: "sub" }, r.requester.email)),
          h("div", { class: "actions" },
            h("button", { class: "btn btn-small btn-primary", type: "button", onclick: (e) =>
              action(e.currentTarget, async () => { await api(`/api/friend-requests/${r.id}/accept`, { method: "POST" }); loadRequests(); }, { success: "Friend request accepted" }) }, "Accept"),
            h("button", { class: "btn btn-small", type: "button", onclick: (e) =>
              action(e.currentTarget, async () => { await api(`/api/friend-requests/${r.id}/reject`, { method: "POST" }); loadRequests(); }, { success: "Request rejected" }) }, "Reject"))),
        "No pending requests.");
    } catch (err) { showLoadError(requestList, err); }
  }

  loadTrips();
  loadRequests();
})();
