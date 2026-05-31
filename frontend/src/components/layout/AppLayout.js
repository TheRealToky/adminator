import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';
export function AppLayout() {
    const [sidebarOpen, setSidebarOpen] = useState(false);
    return (_jsxs("div", { className: "flex min-h-screen bg-slate-50", children: [_jsx(Sidebar, { open: sidebarOpen, onClose: () => setSidebarOpen(false) }), _jsxs("div", { className: "flex-1 flex flex-col min-w-0", children: [_jsx(Topbar, { onMenu: () => setSidebarOpen(true) }), _jsx("main", { className: "flex-1 px-4 sm:px-6 lg:px-8 py-6", children: _jsx(Outlet, {}) })] })] }));
}
