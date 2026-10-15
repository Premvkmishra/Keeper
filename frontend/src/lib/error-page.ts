export function renderErrorPage(): string {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Server Error</title>
  <style>
    body {
      font-family: system-ui, sans-serif;
      max-width: 640px;
      margin: 80px auto;
      padding: 0 24px;
      color: #222;
      line-height: 1.6;
    }
    h1 { font-size: 1.8rem; }
  </style>
</head>
<body>
  <h1>Something went wrong</h1>
  <p>The server encountered an unexpected error. Please try again later.</p>
</body>
</html>`;
}
