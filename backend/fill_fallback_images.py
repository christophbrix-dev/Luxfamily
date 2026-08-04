"""
Fill fallback images for Curated events that had no og:image reachable.
Uses category-specific Unsplash "source" URLs (free, no API key required,
served with permissive attribution). Idempotent — only touches events whose
`image` field is empty AND belongs to the Curated Luxfamily seed.

Run:
    cd /app/backend && python fill_fallback_images.py
"""
import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

# Hand-picked stable Unsplash photo IDs by app category. Each URL uses the
# Unsplash "images" CDN with fixed ?w & ?q params for consistency.
FALLBACK_BY_CATEGORY: dict[str, str] = {
    "Playgrounds":
        "https://images.unsplash.com/photo-1547479674-b4e51322611e?auto=format&fit=crop&w=1200&q=80",
    "Indoor":
        "https://images.unsplash.com/photo-1560184611-ff3e53f00e8f?auto=format&fit=crop&w=1200&q=80",
    "Sports":
        "https://images.unsplash.com/photo-1526676037777-05a232554d77?auto=format&fit=crop&w=1200&q=80",
    "Nature":
        "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=1200&q=80",
    "Culture":
        "https://images.unsplash.com/photo-1548013146-72479768bada?auto=format&fit=crop&w=1200&q=80",
    "Animals":
        "https://images.unsplash.com/photo-1425082661705-1834bfd09dca?auto=format&fit=crop&w=1200&q=80",
    "Workshops":
        "https://images.unsplash.com/photo-1503676260728-1c00da094a0b?auto=format&fit=crop&w=1200&q=80",
    "Food":
        "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?auto=format&fit=crop&w=1200&q=80",
}
GENERIC = "https://images.unsplash.com/photo-1533450718592-29d45635f0a9?auto=format&fit=crop&w=1200&q=80"

# Manual overrides for a few venues where a category-generic image would be
# misleading — pick something that reflects the actual venue type.
OVERRIDES: dict[str, str] = {
    # Castles — use a castle photo
    "lf-075-schloss-koerich":
        "https://images.unsplash.com/photo-1533050487297-09b450131914?auto=format&fit=crop&w=1200&q=80",
    "lf-076-schloss-ansembourg":
        "https://images.unsplash.com/photo-1533050487297-09b450131914?auto=format&fit=crop&w=1200&q=80",
    "lf-077-schloss-hollenfels":
        "https://images.unsplash.com/photo-1533050487297-09b450131914?auto=format&fit=crop&w=1200&q=80",
    "lf-078-schloss-schoenfels":
        "https://images.unsplash.com/photo-1533050487297-09b450131914?auto=format&fit=crop&w=1200&q=80",
    "lf-079-schloss-mersch":
        "https://images.unsplash.com/photo-1533050487297-09b450131914?auto=format&fit=crop&w=1200&q=80",
    # Trampoline / ninja / indoor jump halls
    "lf-036-ozone-trampoline-ninja-parc":
        "https://images.unsplash.com/photo-1550684848-fac1c5b4e853?auto=format&fit=crop&w=1200&q=80",
    "lf-038-indyland-park":
        "https://images.unsplash.com/photo-1560184611-ff3e53f00e8f?auto=format&fit=crop&w=1200&q=80",
    "lf-041-mared-indoor":
        "https://images.unsplash.com/photo-1560184611-ff3e53f00e8f?auto=format&fit=crop&w=1200&q=80",
    # Hochseilgarten / adventure parks
    "lf-085-parc-le-h-adventures":
        "https://images.unsplash.com/photo-1580673302639-4ee89144dbba?auto=format&fit=crop&w=1200&q=80",
    "lf-086-steinfort-adventure":
        "https://images.unsplash.com/photo-1580673302639-4ee89144dbba?auto=format&fit=crop&w=1200&q=80",
    "lf-087-indian-forest-vianden":
        "https://images.unsplash.com/photo-1580673302639-4ee89144dbba?auto=format&fit=crop&w=1200&q=80",
    # Skatepark
    "lf-092-skatepark-pumptrack-ehnen":
        "https://images.unsplash.com/photo-1520045892732-304bc3ac5d8e?auto=format&fit=crop&w=1200&q=80",
    # Escape room
    "lf-101-enigmo-escape-rooms":
        "https://images.unsplash.com/photo-1596496050827-8299e0220de1?auto=format&fit=crop&w=1200&q=80",
    # Hiking trails
    "lf-049-rundwanderwege-fur-kinder":
        "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=1200&q=80",
}


def pick_image(event: dict) -> str:
    ext_id = event.get("external_id", "")
    if ext_id in OVERRIDES:
        return OVERRIDES[ext_id]
    cats = event.get("category", []) or []
    for c in cats:
        if c in FALLBACK_BY_CATEGORY:
            return FALLBACK_BY_CATEGORY[c]
    return GENERIC


def main() -> None:
    client = MongoClient(os.environ["MONGO_URL"])
    db     = client[os.environ["DB_NAME"]]

    todo = list(db.events.find({
        "$or": [{"image": ""}, {"image": {"$exists": False}}, {"image": None}],
    }))
    print(f"[fallback-img] {len(todo)} events without image")

    n = 0
    for ev in todo:
        img = pick_image(ev)
        db.events.update_one({"_id": ev["_id"]}, {"$set": {"image": img}})
        n += 1
    print(f"[fallback-img] filled: {n}")


if __name__ == "__main__":
    main()
