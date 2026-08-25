// Does this record have a photograph of itself?
//
// A photo makes a claim. An event in Kayl showed the Taj Mahal, because the
// backend fills an empty image with a category-generic stock photo and the one
// for "Culture" happens to be an Indian mausoleum. Nothing was broken; the card
// simply asserted something that was not true about the place.
//
// The rest of the app spent the day learning to say "we do not know" rather
// than guess — an unparsed opening time shows no badge, a lake without a size
// is not called a bathing lake. A picture is the loudest claim on the card and
// should follow the same rule.
//
// So: a stock URL counts as no picture, and the card draws a placeholder
// instead. Every image on a real record comes from the source's own og:image
// or from the venue itself; nothing legitimately points at a stock library.

const STOCK_HOSTS = [
  "images.unsplash.com",
  "source.unsplash.com",
  "images.pexels.com",
  "cdn.pixabay.com",
  "via.placeholder.com",
  "placehold.co",
  "picsum.photos",
];

/** Whether this URL is a photograph of the thing it is attached to. */
export function hasOwnPhoto(url: string | null | undefined): boolean {
  const raw = (url ?? "").trim();
  if (!raw) return false;
  if (!/^https?:\/\//i.test(raw)) return false;
  const host = raw.replace(/^https?:\/\//i, "").split("/")[0].toLowerCase();
  return !STOCK_HOSTS.some((s) => host === s || host.endsWith(`.${s}`));
}

/** Icon standing in for a category when there is no photograph. */
export function categoryIcon(type: string | null | undefined): string {
  switch ((type ?? "").toLowerCase()) {
    case "outdoor":
      return "leaf-outline";
    case "indoor":
      return "home-outline";
    case "educational":
      return "school-outline";
    case "event":
      return "sparkles-outline";
    default:
      return "location-outline";
  }
}
