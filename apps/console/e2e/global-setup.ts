const endpoints = [
  "http://localhost:3000/",
  "http://localhost:8080/livez",
  "http://localhost:8081/realms/dusk-local/.well-known/openid-configuration",
];

export default async function globalSetup() {
  const deadline = Date.now() + 60_000;
  for (const endpoint of endpoints) {
    let ready = false;
    while (Date.now() < deadline) {
      try {
        const response = await fetch(endpoint);
        if (response.ok) {
          ready = true;
          break;
        }
      } catch {
        // The bounded retry handles containers that are still starting.
      }
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
    if (!ready)
      throw new Error(`Local E2E dependency is unavailable: ${endpoint}`);
  }
}
