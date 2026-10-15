export function pageHead(title: string, description?: string) {
  const fullTitle = `${title} — Keeper`;
  return {
    meta: [
      { title: fullTitle },
      ...(description
        ? [
            { name: "description", content: description },
            { property: "og:title", content: fullTitle },
            { property: "og:description", content: description },
          ]
        : []),
    ],
  };
}
