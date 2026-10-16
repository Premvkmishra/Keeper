export function pageHead(title: string, description: string) {
  const t = `${title} — Keeper`;
  return {
    meta: [
      { title: t },
      { name: "description", content: description },
      { property: "og:title", content: t },
      { property: "og:description", content: description },
    ],
  };
}
