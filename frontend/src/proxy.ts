import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function proxy(request: NextRequest) {
  const backendApiUrl =
    process.env.BACKEND_API_URL ?? "http://localhost:8080";
  const destination = new URL(
    request.nextUrl.pathname + request.nextUrl.search,
    backendApiUrl,
  );
  return NextResponse.rewrite(destination);
}

export const config = {
  matcher: "/api/:path*",
};
