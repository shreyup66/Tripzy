"""Browser end-to-end tests. Run with: pytest tests/e2e  (needs `playwright install chromium`)."""

import re

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import unique_email

pytestmark = pytest.mark.e2e
PASSWORD = "Passw0rd!"


def ui_signup(page: Page, name: str) -> str:
    email = unique_email(name)
    page.goto("/signup")
    page.get_by_label("Display name").fill(name)
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password").fill(PASSWORD)
    page.get_by_role("button", name="Sign up").click()
    expect(page).to_have_url(re.compile(r"/dashboard$"))
    return email


def api_signup(context, name: str) -> str:
    email = unique_email(name)
    r = context.request.post("/api/auth/signup", data={"display_name": name, "email": email, "password": PASSWORD})
    assert r.status == 201, r.text()
    return email


def ui_create_trip(page: Page, name="Goa Weekend", destination="North Goa, India") -> None:
    page.goto("/trips")
    page.get_by_label("Trip name").fill(name)
    page.get_by_label("Destination").fill(destination)
    page.get_by_label("Start date").fill("2026-12-11")
    page.get_by_label("End date").fill("2026-12-14")
    page.get_by_role("button", name="Create trip").click()
    expect(page).to_have_url(re.compile(r"/trips/\d+$"))
    expect(page.locator("#trip-title")).to_have_text(name)


def test_auth_validation_messages(new_context):
    page = new_context().new_page()
    page.goto("/signup")
    page.get_by_label("Display name").fill("Weak")
    page.get_by_label("Email").fill(unique_email("weak"))
    page.get_by_label("Password").fill("short")
    page.get_by_role("button", name="Sign up").click()
    expect(page.locator(".form-error")).to_contain_text("at least 8 characters")
    expect(page.get_by_label("Display name")).to_have_value("Weak")  # input preserved
    page.goto("/dashboard")
    expect(page).to_have_url(re.compile(r"/login\?next=/dashboard"))


def test_trip_members_budget_and_locations_flow(new_context):
    """Walks TM-01, TM-02, BS-01..BS-06, TM-03, LS-01, LS-02, TM-04 through the real UI."""
    blair_ctx = new_context()
    blair_email = api_signup(blair_ctx, "Blair")

    page = new_context().new_page()
    page.on("dialog", lambda d: d.accept())  # confirm destructive actions
    ui_signup(page, "Alex")

    # TM-01 create trip, TM-02 add member
    ui_create_trip(page)
    trip_url = page.url
    page.get_by_label("…or enter their Tripzy email").fill(blair_email)
    page.get_by_role("button", name="Add member").click()
    expect(page.locator("#member-list")).to_contain_text("Blair")

    # BS-01 / BS-03 equal split among all members
    page.get_by_role("link", name="Budget Splitter").first.click()
    page.get_by_label("Description").fill("Dinner")
    page.get_by_label("Amount (₹)").fill("900")
    expect(page.locator("#split-status")).to_contain_text("2 people · ₹450.00 each")
    page.get_by_role("button", name="Save expense").click()
    expense_list = page.locator("#expense-list")
    expect(expense_list).to_contain_text("Dinner")
    expect(expense_list).to_contain_text("Alex ₹450.00")
    expect(expense_list).to_contain_text("Blair ₹450.00")
    expect(page.locator("#settlements")).to_contain_text("Blair pays Alex")
    expect(page.locator("#settlements")).to_contain_text("₹450.00")

    # BS-02 negative amount
    page.get_by_label("Description").fill("Refund?")
    page.get_by_label("Amount (₹)").fill("-50")
    page.get_by_role("button", name="Save expense").click()
    expect(page.locator("#expense-form .form-error")).to_have_text("Enter a valid amount")
    expect(page.get_by_label("Amount (₹)")).to_have_value("-50")

    # BS-05 custom shares with live total check
    page.get_by_label("Description").fill("Cab")
    page.get_by_label("Amount (₹)").fill("500")
    page.get_by_label("Custom shares").check()
    page.get_by_label("Share for Alex").fill("100")
    page.get_by_label("Share for Blair").fill("300")
    expect(page.locator("#split-status")).to_contain_text("₹100.00 left to assign")
    page.get_by_label("Share for Blair").fill("400")
    expect(page.locator("#split-status")).to_contain_text("matches the expense amount")
    page.get_by_role("button", name="Save expense").click()
    expect(expense_list).to_contain_text("Cab")
    expect(page.locator("#balances")).to_contain_text("−₹850.00")  # Blair: 450 + 400

    # BS-04 selected members only
    page.get_by_label("Split equally").check()
    page.get_by_label("Description").fill("Snacks")
    page.get_by_label("Amount (₹)").fill("120")
    page.get_by_label("Include Blair").uncheck()
    page.get_by_role("button", name="Save expense").click()
    expect(expense_list).to_contain_text("Snacks")
    snacks = expense_list.locator("li", has_text="Snacks")
    expect(snacks).to_contain_text("Alex ₹120.00")
    expect(snacks).not_to_contain_text("Blair")

    # BS-06 delete expense, balances update
    expense_list.locator("li", has_text="Cab").get_by_role("button", name="Delete").click()
    expect(expense_list).not_to_contain_text("Cab")
    expect(page.locator("#balances")).to_contain_text("−₹450.00")

    # LS-02 suggestions, LS-01 save
    page.get_by_role("link", name="Locations").first.click()
    results = page.locator("#results")
    expect(results).to_contain_text("Baga Beach")
    expect(page.locator("#results-meta")).to_contain_text("Demo data")
    results.locator("article", has_text="Fort Aguada").get_by_role("button", name="Save to trip").click()
    expect(page.locator("#saved-list")).to_contain_text("Fort Aguada")
    page.get_by_label("Destination, city or keyword").fill("Jaipur")
    page.get_by_role("button", name="Search").click()
    expect(results).to_contain_text("Hawa Mahal")

    # Saved place shows on the overview; TM-03 remove member (needs no expenses, so delete Dinner first)
    page.goto(trip_url + "/budget")
    page.locator("#expense-list li", has_text="Dinner").get_by_role("button", name="Delete").click()
    expect(page.locator("#expense-list")).not_to_contain_text("Dinner")
    page.goto(trip_url)
    expect(page.locator("#saved-summary")).to_contain_text("Fort Aguada")
    page.locator("#member-list li", has_text="Blair").get_by_role("button", name="Remove member").click()
    expect(page.locator("#member-list")).not_to_contain_text("Blair")

    # TM-04 delete trip
    page.get_by_role("button", name="Delete trip").click()
    expect(page).to_have_url(re.compile(r"/trips$"))
    expect(page.locator("#trip-list")).to_contain_text("No trips yet")


def test_friends_and_groups_flow(new_context):
    blair_ctx = new_context()
    blair_page = blair_ctx.new_page()
    blair_email = ui_signup(blair_page, "Blair")

    page = new_context().new_page()
    page.on("dialog", lambda d: d.accept())
    ui_signup(page, "Alex")
    page.goto("/friends")
    page.get_by_label("Name or email").fill(blair_email)
    page.get_by_role("button", name="Search").click()
    page.locator("#search-results li", has_text=blair_email).get_by_role("button", name="Add friend").click()
    expect(page.locator("#outgoing-list")).to_contain_text("Blair")

    blair_page.goto("/dashboard")
    blair_page.locator("#dash-request-list li", has_text="Alex").get_by_role("button", name="Accept").click()
    expect(blair_page.locator("#dash-request-list")).to_contain_text("No pending requests")

    page.goto("/groups")
    page.get_by_label("Group name").first.fill("Goa gang")
    page.get_by_role("button", name="Create group").click()
    card = page.locator("section.card", has_text="Goa gang")
    card.get_by_label("Add a friend").select_option(label=f"Blair ({blair_email})")
    card.get_by_role("button", name="Add").click()
    expect(page.locator("section.card", has_text="Goa gang").locator("ul.list")).to_contain_text("Blair")

    # Group preselects trip members on the create-trip form
    page.goto("/trips")
    page.get_by_label("Preselect from a friend group").select_option(label="Goa gang (1)")
    expect(page.get_by_label(re.compile("Blair"))).to_be_checked()


# ---------------- LS-03 / LS-04: browser geolocation ----------------


def _open_locations(page: Page) -> None:
    ui_signup(page, "Geo")
    ui_create_trip(page, name="Somewhere", destination="Unknown Place")
    page.get_by_role("link", name="Locations").first.click()
    expect(page.locator("#results-meta")).to_contain_text("Popular places for")


def test_geolocation_granted_uses_location(new_context):
    """LS-03: Use My Location + allow -> nearby suggestions based on the device location."""
    ctx = new_context(permissions=["geolocation"], geolocation={"latitude": 15.4989, "longitude": 73.8278})
    page = ctx.new_page()
    _open_locations(page)
    page.get_by_role("button", name="Use my location").click()
    expect(page.locator("#geo-explainer")).to_contain_text("Why we ask")  # explained before the prompt
    page.get_by_role("button", name="Continue").click()
    expect(page.locator("#results-meta")).to_contain_text("Popular places near you")
    expect(page.locator("#results")).to_contain_text("near 15.50, 73.83")
    expect(page.locator("#geo-message")).to_be_hidden()


def test_geolocation_denied_shows_message(new_context, server_url):
    """LS-04: Deny the browser prompt -> permission-denied message; destination search still works."""
    ctx = new_context()
    ctx.clear_permissions()
    page = ctx.new_page()
    # Simulate the user pressing "Block" on the browser prompt.
    page.add_init_script("""
        navigator.geolocation.getCurrentPosition = (ok, fail) =>
          setTimeout(() => fail({ code: 1, PERMISSION_DENIED: 1, POSITION_UNAVAILABLE: 2, TIMEOUT: 3 }), 50);
    """)
    _open_locations(page)
    page.get_by_role("button", name="Use my location").click()
    page.get_by_role("button", name="Continue").click()
    expect(page.locator("#geo-message")).to_have_text(
        "Location permission denied. You can still search using your trip destination.")
    expect(page.locator("#results-meta")).to_contain_text("Popular places for “Unknown Place”")
    # No second prompt after denial.
    page.get_by_role("button", name="Use my location").click()
    expect(page.locator("#geo-explainer")).to_be_hidden()
    expect(page.locator("#geo-message")).to_contain_text("permission denied")
    # Manual search still works.
    page.get_by_label("Destination, city or keyword").fill("Mumbai")
    page.get_by_role("button", name="Search").click()
    expect(page.locator("#results")).to_contain_text("Gateway of India")


def test_geolocation_unsupported(new_context):
    page = new_context().new_page()
    page.add_init_script("delete Navigator.prototype.geolocation;")
    _open_locations(page)
    page.get_by_role("button", name="Use my location").click()
    expect(page.locator("#geo-message")).to_contain_text("not supported")
