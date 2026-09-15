import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { ProtectedRoute } from "@/components/layout/ProtectedRoute";
import { Login } from "@/pages/Login";
import { Register } from "@/pages/Register";
import { ForgotPassword } from "@/pages/ForgotPassword";
import { ResetPassword } from "@/pages/ResetPassword";
import { RoleRedirect } from "@/pages/RoleRedirect";
import { MyTickets } from "@/pages/MyTickets";
import { NewTicket } from "@/pages/NewTicket";
import { TicketDetail } from "@/pages/TicketDetail";
import { AdminQueue } from "@/pages/AdminQueue";
import { Dashboard } from "@/pages/Dashboard";
import { IssuesList } from "@/pages/IssuesList";
import { IssueDetail } from "@/pages/IssueDetail";
import { HelpCenter } from "@/pages/HelpCenter";
import { HelpCenterArticle } from "@/pages/HelpCenterArticle";
import { AdminAccess } from "@/pages/AdminAccess";
import { Profile } from "@/pages/Profile";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />

        <Route
          element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }
        >
          <Route path="/" element={<RoleRedirect />} />
          <Route path="/profile" element={<Profile />} />

          <Route path="/tickets" element={<ProtectedRoute allow={["staff"]}><MyTickets /></ProtectedRoute>} />
          <Route path="/tickets/new" element={<ProtectedRoute allow={["staff"]}><NewTicket /></ProtectedRoute>} />
          <Route path="/tickets/:id" element={<TicketDetail />} />
          <Route path="/help-center" element={<ProtectedRoute allow={["staff"]}><HelpCenter /></ProtectedRoute>} />
          <Route path="/help-center/:id" element={<ProtectedRoute allow={["staff"]}><HelpCenterArticle /></ProtectedRoute>} />

          <Route path="/queue" element={<ProtectedRoute allow={["admin"]}><AdminQueue /></ProtectedRoute>} />
          <Route path="/dashboard" element={<ProtectedRoute allow={["admin"]}><Dashboard /></ProtectedRoute>} />
          <Route path="/issues" element={<ProtectedRoute allow={["admin"]}><IssuesList /></ProtectedRoute>} />
          <Route path="/issues/:id" element={<ProtectedRoute allow={["admin"]}><IssueDetail /></ProtectedRoute>} />
          <Route path="/admin-access" element={<ProtectedRoute allow={["admin"]}><AdminAccess /></ProtectedRoute>} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
