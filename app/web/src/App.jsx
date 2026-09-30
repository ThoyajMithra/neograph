import AppLayout from "./components/layout/layout";
import { AppProvider } from "./context/AppContext";

export default function App() {
  return (
    <AppProvider>
      <AppLayout />
    </ AppProvider >
  );
}
