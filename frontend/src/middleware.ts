import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
    const thread_id = request.cookies.get("threadID");

    if(thread_id) {
        return NextResponse.next();
    }

    const response = NextResponse.next();
    response.cookies.set("threadID", crypto.randomUUID());

    return response;
}

export const config = {
    matcher: ["/"],
};