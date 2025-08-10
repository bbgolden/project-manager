import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
    const thread_id = request.cookies.get("thread_id");

    if(thread_id) {
        return NextResponse.next();
    }

    const response = NextResponse.next();
    response.cookies.set("thread_id", crypto.randomUUID());

    return response;
}

export const config = {
    matcher: ["/"],
};