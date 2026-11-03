import { useEffect } from "react";

import AppLayout from "./components/layout/layout";
import { AppProvider } from "./context/AppContext";

export default function App() {
  useEffect(() => {
      fetch("/api/visitor", {
          method: "POST"
      });
  }, []);
  return (
    <AppProvider>
      <AppLayout />
    </ AppProvider >
  );
}
