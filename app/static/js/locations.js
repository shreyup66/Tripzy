(function () {
  const { api, h, renderList, showLoadError, action, bindForm, toast, safeHref } = window.Tripzy;
  const { id: tripId, destination } = window.TRIP;
  const base = `/api/trips/${tripId}/locations`;
  const resultsEl = document.getElementById("results");
  const metaEl = document.getElementById("results-meta");
  const savedEl = document.getElementById("saved-list");
  const geoBtn = document.getElementById("use-location-btn");
  const explainer = document.getElementById("geo-explainer");
  const geoMessage = document.getElementById("geo-message");
  let lastSearch = { query: destination };
  let locationDenied = false;

  function showGeoMessage(text) {
    geoMessage.textContent = text;
    geoMessage.hidden = !text;
  }

  function placeCard(p) {
    const href = safeHref(p.provider_url);
    const saveBtn = h("button", { class: "btn btn-small btn-primary", type: "button", disabled: p.saved }, p.saved ? "Saved" : "Save to trip");
    saveBtn.addEventListener("click", () =>
      action(saveBtn, async () => {
        await api(base, {
          method: "POST",
          body: { provider_place_id: p.provider_place_id, name: p.name, category: p.category, address: p.address, provider_url: href },
        });
        p.saved = true;
        loadSaved();
      }, { success: `${p.name} saved to the trip` }).then(() => {
        if (p.saved) { saveBtn.disabled = true; saveBtn.textContent = "Saved"; }
      }));
    return h("article", { class: "place" },
      h("div", { class: "title" }, p.name),
      p.category ? h("div", { class: "meta" }, p.category) : null,
      p.address ? h("div", { class: "meta" }, p.address) : null,
      p.rating != null ? h("div", { class: "meta" }, `Rating ${Number(p.rating).toFixed(1)} / 5`) : null,
      h("div", { class: "place-actions" }, saveBtn,
        href ? h("a", { href, target: "_blank", rel: "noopener noreferrer" }, "View on map") : null));
  }

  async function search(params) {
    lastSearch = params;
    const qs = new URLSearchParams();
    if (params.query) qs.set("query", params.query);
    if (params.latitude != null) { qs.set("latitude", params.latitude); qs.set("longitude", params.longitude); }
    metaEl.textContent = "Loading suggestions…";
    resultsEl.setAttribute("aria-busy", "true");
    resultsEl.replaceChildren();
    try {
      const data = await api(`${base}/suggestions?${qs}`);
      const label = data.near_me ? "Popular places near you" : `Popular places for “${data.query}”`;
      metaEl.replaceChildren(h("span", {}, label,
        data.demo ? h("span", { class: "badge", style: "margin-left:.5rem" }, "Demo data") : null,
        data.attribution ? h("span", { class: "hint", style: "display:block" }, data.attribution) : null));
      resultsEl.replaceChildren(...(data.results.length
        ? data.results.map(placeCard)
        : [h("p", { class: "muted" }, "No places found. Try a different destination or keyword.")]));
    } catch (err) {
      metaEl.textContent = "";
      resultsEl.replaceChildren(h("div", { class: "notice notice-warn" },
        h("p", {}, err.message),
        h("button", { class: "btn btn-small", type: "button", onclick: () => search(lastSearch) }, "Try again")));
    } finally {
      resultsEl.removeAttribute("aria-busy");
    }
  }

  async function loadSaved() {
    try {
      const places = await api(base);
      renderList(savedEl, places, (p) => {
        const href = safeHref(p.provider_url);
        return h("li", {},
          h("div", { class: "grow" },
            href ? h("a", { class: "title", href, target: "_blank", rel: "noopener noreferrer" }, p.name) : h("span", { class: "title" }, p.name),
            h("div", { class: "sub" }, [p.category, p.address].filter(Boolean).join(" · "))),
          h("button", { class: "btn btn-small", type: "button", onclick: (e) =>
            action(e.currentTarget, async () => {
              await api(`${base}/${p.id}`, { method: "DELETE" });
              loadSaved();
              search(lastSearch);
            }, { confirm: `Remove ${p.name} from this trip?`, success: "Place removed" }) }, "Remove"));
      }, "Nothing saved yet. Save places from the suggestions.");
    } catch (err) { showLoadError(savedEl, err); }
  }

  bindForm(document.getElementById("place-search-form"), async (values) => {
    showGeoMessage("");
    await search({ query: (values.query || "").trim() || destination });
  });

  /* Geolocation is opt-in: explain first, then let the browser prompt. Never re-prompt after denial. */
  function requestNearbyPlaces(onSuccess, onError) {
    if (!("geolocation" in navigator)) {
      onError("Location is not supported by this browser. Search by destination instead.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => onSuccess({ latitude: position.coords.latitude, longitude: position.coords.longitude }),
      (error) => {
        if (error.code === error.PERMISSION_DENIED) {
          locationDenied = true;
          onError("Location permission denied. You can still search using your trip destination.");
        } else if (error.code === error.TIMEOUT) {
          onError("Location request timed out. Try again or search by destination.");
        } else {
          onError("Unable to determine your location. Search by destination instead.");
        }
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 }
    );
  }

  async function permissionDenied() {
    if (locationDenied) return true;
    try {
      const status = await navigator.permissions?.query({ name: "geolocation" });
      return status?.state === "denied";
    } catch {
      return false;
    }
  }

  geoBtn.addEventListener("click", async () => {
    showGeoMessage("");
    if (!("geolocation" in navigator)) {
      showGeoMessage("Location is not supported by this browser. Search by destination instead.");
      return;
    }
    if (await permissionDenied()) {
      locationDenied = true;
      showGeoMessage("Location permission denied. You can still search using your trip destination. To use your location, allow it in your browser's site settings.");
      return;
    }
    explainer.hidden = false;
    document.getElementById("geo-continue").focus();
  });

  document.getElementById("geo-cancel").addEventListener("click", () => {
    explainer.hidden = true;
    geoBtn.focus();
  });

  document.getElementById("geo-continue").addEventListener("click", (e) => {
    const btn = e.currentTarget;
    btn.disabled = true;
    metaEl.textContent = "Getting your location…";
    requestNearbyPlaces(
      (coords) => {
        btn.disabled = false;
        explainer.hidden = true;
        // Coordinates are used for this request only and never saved.
        search({ latitude: coords.latitude.toFixed(4), longitude: coords.longitude.toFixed(4) });
        toast("Showing places near you");
      },
      (message) => {
        btn.disabled = false;
        explainer.hidden = true;
        search(lastSearch); // keep destination-based results available
        showGeoMessage(message);
        geoBtn.focus();
      }
    );
  });

  loadSaved();
  search({ query: destination });
})();
