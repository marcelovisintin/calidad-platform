import { Navigate, RouterProvider, createBrowserRouter } from "react-router-dom";
import { HomeRedirect } from "../components/HomeRedirect";
import { ProtectedRoute } from "../components/ProtectedRoute";
import { AppLayout } from "../layouts/AppLayout";
import { ChangePasswordPage } from "../modules/accounts/pages/ChangePasswordPage";
import { LoginPage } from "../modules/accounts/pages/LoginPage";
import { CatalogManagementPage } from "../modules/admin/pages/CatalogManagementPage";
import { UserBulkImportPage } from "../modules/admin/pages/UserBulkImportPage";
import { UserManagementPage } from "../modules/admin/pages/UserManagementPage";
import { UserScopesPage } from "../modules/admin/pages/UserScopesPage";
import { MyActionsPage } from "../modules/actions/pages/MyActionsPage";
import { AnomalyCreatedPage } from "../modules/anomalies/pages/AnomalyCreatedPage";
import { AffectedOrdersPage } from "../modules/anomalies/pages/AffectedOrdersPage";
import { AnomalyDetailPage } from "../modules/anomalies/pages/AnomalyDetailPage";
import { AnomalyRepetitionStudyPage } from "../modules/anomalies/pages/AnomalyRepetitionStudyPage";
import { MyAnomaliesPage } from "../modules/anomalies/pages/MyAnomaliesPage";
import { ImmediateActionsPage } from "../modules/anomalies/pages/ImmediateActionsPage";
import { NewAnomalyPage } from "../modules/anomalies/pages/NewAnomalyPage";
import { DashboardPage } from "../modules/dashboard/pages/DashboardPage";
import { TreatmentsPage } from "../modules/treatments/pages/TreatmentsPage";
import { LearnedLessonsPage } from "../modules/treatments/pages/LearnedLessonsPage";
import { TreatmentTrackingPage } from "../modules/treatments/pages/TreatmentTrackingPage";
import { TreatmentValidationPage } from "../modules/treatments/pages/TreatmentValidationPage";
import { InboxPage } from "../modules/notifications/pages/InboxPage";
import { IndicatorDashboardPage } from "../modules/indicators/pages/IndicatorDashboardPage";
import { IndicatorsPage } from "../modules/indicators/pages/IndicatorsPage";
import { HelpCenterPage } from "../modules/help/pages/HelpCenterPage";

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
      { path: "dashboard/summary", element: <DashboardPage defaultView="overview" /> },
      { path: "anomalies", element: <MyAnomaliesPage /> },
      { path: "anomalies/observations", element: <ImmediateActionsPage /> },
      { path: "anomalies/immediate-actions", element: <ImmediateActionsPage /> },
      { path: "anomalies/repetition-study", element: <AnomalyRepetitionStudyPage /> },
      { path: "anomalies/new", element: <NewAnomalyPage /> },
      { path: "anomalies/created", element: <AnomalyCreatedPage /> },
      { path: "affected-orders", element: <AffectedOrdersPage /> },
      { path: "indicators", element: <IndicatorsPage /> },
      { path: "indicators/:indicatorKey", element: <IndicatorDashboardPage /> },
      { path: "anomalies/:anomalyId", element: <AnomalyDetailPage /> },
      { path: "treatments", element: <TreatmentsPage /> },
      { path: "treatments/tracking", element: <TreatmentTrackingPage /> },
      { path: "learned-lessons", element: <LearnedLessonsPage /> },
      { path: "actions/mine", element: <MyActionsPage /> },
      { path: "validation", element: <TreatmentValidationPage /> },
      { path: "tasks", element: <Navigate replace to="/notifications/inbox?tab=pending" /> },
      { path: "notifications/inbox", element: <InboxPage /> },
      { path: "help", element: <HelpCenterPage /> },
      { path: "management/users", element: <UserManagementPage /> },
      { path: "management/users/import", element: <UserBulkImportPage /> },
      { path: "management/user-scopes", element: <UserScopesPage /> },
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

