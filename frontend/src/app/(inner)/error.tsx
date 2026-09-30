"use client"; // Error boundaries must be Client Components

// Lives inside each route group so the page header stays visible when a page fails.
export { default } from "@/components/ErrorView";
