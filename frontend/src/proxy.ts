import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { BACKEND_API_URL } from "@/lib/config";

export function proxy(request: NextRequest) {
  const destination = new URL(
    request.nextUrl.pathname + request.nextUrl.search,
    BACKEND_API_URL,
  );
  return NextResponse.rewrite(destination);
}

export const config = {
  matcher: "/api/:path*",
};
