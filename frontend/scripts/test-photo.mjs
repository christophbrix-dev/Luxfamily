// Tests for "does this record have a photograph of itself?".
//
// An event in Kayl showed the Taj Mahal, because the backend filled every
// empty image with a category-generic stock photo and the one for "Culture"
// is an Indian mausoleum. Nothing was broken; the card simply asserted
// something untrue about the place.
//
//   node --experimental-strip-types scripts/test-photo.mjs

import { hasOwnPhoto, categoryIcon } from "../src/utils/photo.ts";

let failures = 0;
function check(name, actual, expected) {
  if (actual !== expected) {
    failures += 1;
    console.log(`  FAIL  ${name}\n        expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

// --- a real photograph --------------------------------------------------
check("a commune's own image", hasOwnPhoto("https://petange.lu/wp-content/uploads/fest.jpg"), true);
check("a venue's og:image", hasOwnPhoto("https://www.rockhal.lu/media/show.png"), true);
check("http as well as https", hasOwnPhoto("http://mamer.lu/img/a.jpg"), true);

// --- stock libraries ----------------------------------------------------
// The exact URL that produced the Taj Mahal.
check("the Taj Mahal itself",
  hasOwnPhoto("https://images.unsplash.com/photo-1548013146-72479768bada?auto=format&w=1200"), false);
for (const host of [
  "images.unsplash.com", "source.unsplash.com", "images.pexels.com",
  "cdn.pixabay.com", "via.placeholder.com", "placehold.co", "picsum.photos",
]) {
  check(`stock: ${host}`, hasOwnPhoto(`https://${host}/photo-123.jpg`), false);
}

// --- nothing at all -----------------------------------------------------
check("empty", hasOwnPhoto(""), false);
check("whitespace", hasOwnPhoto("   "), false);
check("missing", hasOwnPhoto(null), false);
check("undefined", hasOwnPhoto(undefined), false);
check("not a URL", hasOwnPhoto("fest.jpg"), false);
check("a data URI", hasOwnPhoto("data:image/png;base64,AAAA"), false);

// --- the host must match, not merely appear -----------------------------
// A commune that happens to have the word in its path is not a stock library.
check("stock word in the path",
  hasOwnPhoto("https://mamer.lu/images.unsplash.com/a.jpg"), true);
check("a lookalike domain",
  hasOwnPhoto("https://images.unsplash.com.example.invalid/a.jpg"), true);
check("a genuine subdomain",
  hasOwnPhoto("https://eu.images.unsplash.com/a.jpg"), false);

// --- the placeholder icon -----------------------------------------------
check("outdoor", categoryIcon("Outdoor"), "leaf-outline");
check("indoor", categoryIcon("Indoor"), "home-outline");
check("educational", categoryIcon("Educational"), "school-outline");
check("event", categoryIcon("Event"), "sparkles-outline");
check("case does not matter", categoryIcon("outdoor"), "leaf-outline");
check("something unexpected", categoryIcon("Zirkus"), "location-outline");
check("nothing", categoryIcon(null), "location-outline");

const total = 26;
if (failures) {
  console.log(`\n  ${failures} of ${total} checks failed`);
  process.exit(1);
}
console.log(`  photos: ${total} checks passed`);
