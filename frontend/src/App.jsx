import { Link, Outlet, Route, Routes } from "react-router-dom";
import Header from "./components/Header";
import { RequireAuth } from "./components/ui";
import CampsiteDetail from "./pages/CampsiteDetail";
import Campsites from "./pages/Campsites";
import ChatPlaceholder from "./pages/ChatPlaceholder";
import Dashboard from "./pages/Dashboard";
import GroupDetail from "./pages/GroupDetail";
import Groups from "./pages/Groups";
import Feed from "./pages/Feed";
import PostDetail from "./pages/PostDetail";
import Login from "./pages/Login";
import MySubmissions from "./pages/MySubmissions";
import Privacy from "./pages/Privacy";
import Profile from "./pages/Profile";
import { QuestionDetail, QuestionList } from "./pages/Questions";
import Register from "./pages/Register";
import SuggestCampsite from "./pages/SuggestCampsite";
import TripDetail from "./pages/TripDetail";
import TripForm from "./pages/TripForm";
import Trips from "./pages/Trips";

function Shell() {
  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1"><Outlet /></main>
      <footer className="border-t border-slate-200 bg-white py-6 text-center text-xs text-ink/55">
        AdventureHive · a student project at AIT · Map data © OpenStreetMap contributors ·{" "}
        <Link to="/privacy" className="hover:text-forest-800">Privacy (PDPA)</Link>
      </footer>
    </div>
  );
}

const Private = ({ children }) => <RequireAuth>{children}</RequireAuth>;

function NotFound() {
  return (
    <div className="mx-auto max-w-md px-4 py-20 text-center">
      <h1 className="text-2xl font-extrabold">Page not found</h1>
      <p className="mt-2 text-ink/65">The link may be broken, or the page was removed.</p>
      <Link to="/" className="btn-primary mt-6">Go to the home page</Link>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route element={<Shell />}>
        <Route index element={<Dashboard />} />
        <Route path="campsites" element={<Campsites />} />
        <Route path="campsites/new" element={<Private><SuggestCampsite /></Private>} />
        <Route path="campsites/:id" element={<CampsiteDetail />} />
        <Route path="campsites/:id/edit" element={<Private><SuggestCampsite /></Private>} />
        <Route path="my/submissions" element={<Private><MySubmissions /></Private>} />
        <Route path="trips" element={<Trips />} />
        <Route path="trips/new" element={<Private><TripForm /></Private>} />
        <Route path="trips/:id" element={<TripDetail />} />
        <Route path="trips/:id/edit" element={<Private><TripForm /></Private>} />
        <Route path="groups" element={<Groups />} />
        <Route path="groups/:id" element={<GroupDetail />} />
        <Route path="groups/:id/chat" element={<Private><ChatPlaceholder /></Private>} />
        <Route path="messages" element={<Private><ChatPlaceholder /></Private>} />
        <Route path="feed" element={<Private><Feed /></Private>} />
        <Route path="posts/:id" element={<PostDetail />} />
        <Route path="questions" element={<QuestionList />} />
        <Route path="questions/:id" element={<QuestionDetail />} />
        <Route path="profile" element={<Private><Profile /></Private>} />
        <Route path="privacy" element={<Privacy />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
