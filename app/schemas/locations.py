from app.schemas.common import Strict, optional_text, text


class SavedLocationIn(Strict):
    provider_place_id: optional_text(200) = None
    name: text(200)
    category: optional_text(100) = None
    address: optional_text(300) = None
    provider_url: optional_text(500) = None
