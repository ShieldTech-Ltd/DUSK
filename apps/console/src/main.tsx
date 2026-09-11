import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { createRoot } from "react-dom/client";
import { AuthProvider, useAuth } from "./auth";
import { setTokenProvider } from "./api/client";
import { router } from "./router";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 10_000 } },
});
function ConnectedRouter() {
  const auth = useAuth();
  setTokenProvider(() => auth.token);
  return <RouterProvider router={router} />;
}
createRoot(document.getElementById("root")!).render(
  <AuthProvider>
    <QueryClientProvider client={queryClient}>
      <ConnectedRouter />
    </QueryClientProvider>
  </AuthProvider>,
);
