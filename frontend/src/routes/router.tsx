import { Navigate, RouterProvider, createBrowserRouter } from "react-router-dom";
import { HomeRedirect } from "../components/HomeRedirect";
import { ProtectedRoute } from "../components/ProtectedRoute";
import { AppLayout } from "../layouts/AppLayout";
import { ChangePasswordPage } from "../modules/accounts/pages/ChangePasswordPage";
import { LoginPage } from "../modules/accounts/pages/LoginPage";
import { CatalogManagementPage } from "../modules/admin/pages/CatalogManagementPage";
import { UserManagementPage } from "../modules/admin/pages/UserManagementPage";
import { MyActionsPage } from "../modules/actions/pages/MyActionsPage";
import { AnomalyCreatedPage } from "../modules/anomalies/pages/AnomalyCreatedPage";
import { AnomalyDetailPage } from "../modules/anomalies/pages/AnomalyDetailPage";
import { MyAnomaliesPage } from "../modules/anomalies/pages/MyAnomaliesPage";
import { ImmediateActionsPage } from "../modules/anomalies/pages/ImmediateActionsPage";
import { NewAnomalyPage } from "../modules/anomalies/pages/NewAnomalyPage";
import { DashboardPage } from "../modules/dashboard/pages/DashboardPage";
import { TreatmentsPage } from "../modules/treatments/pages/TreatmentsPage";
import { InboxPage } from "../modules/notifications/pages/InboxPage";
import { PendingTasksPage } from "../modules/notifications/pages/PendingTasksPage";

export const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/change-password",
    element: (
      <ProtectedRoute>
        <ChangePasswordPage />
      </ProtectedRoute>
    ),
  },
  {
    path: "/",
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <HomeRedirect /> },
      { path: "dashboard", element: <DashboardPage /> },
      { path: "anomalies", element: <MyAnomaliesPage /> },
      { path: "anomalies/immediate-actions", element: <ImmediateActionsPage /> },
      { path: "anomalies/new", element: <NewAnomalyPage /> },
      { path: "anomalies/created", element: <AnomalyCreatedPage /> },
      { path: "anomalies/:anomalyId", element: <AnomalyDetailPage /> },
      { path: "treatments", element: <TreatmentsPage /> },
      { path: "actions/mine", element: <MyActionsPage /> },
      { path: "tasks", element: <PendingTasksPage /> },
      { path: "notifications/inbox", element: <InboxPage /> },
      { path: "management/users", element: <UserManagementPage /> },
      { path: "management/catalogs", element: <CatalogManagementPage /> },
    ],
  },
  {
    path: "*",
    element: <Navigate replace to="/" />,
  },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}

