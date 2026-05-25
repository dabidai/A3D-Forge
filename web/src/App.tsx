import { Routes, Route } from "react-router-dom";
import AppLayout from "./components/Layout/AppLayout";
import Dashboard from "./pages/Dashboard";
import Generate from "./pages/Generate";
import Repair from "./pages/Repair";
import Assets from "./pages/Assets";
import Logs from "./pages/Logs";

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/generate" element={<Generate />} />
        <Route path="/repair" element={<Repair />} />
        <Route path="/assets" element={<Assets />} />
        <Route path="/logs" element={<Logs />} />
      </Route>
    </Routes>
  );
}
