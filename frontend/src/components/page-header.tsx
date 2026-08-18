import { Link } from "@tanstack/react-router";

import { ThemeToggle } from "@/components/theme-toggle";

export function PageHeader() {
  return (
    <header className="border-b bg-card">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 sm:px-6">
        <Link to="/" className="block">
          <h1 className="text-lg font-semibold tracking-tight sm:text-xl">EGG - Sales Lead</h1>
          <p className="text-xs text-muted-foreground sm:text-sm">Internal sales dashboard</p>
        </Link>
        <ThemeToggle />
      </div>
    </header>
  );
}
