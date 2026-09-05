import { SignJWT } from "jose";

export async function mintServiceToken(userId: string, role: string = "user"){
    const secret = new TextEncoder().encode(process.env.FASTAPI_JWT_SECRET!);
    return await new SignJWT({role})
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(userId)
    .setIssuedAt()
    .setExpirationTime("5m")
    .sign(secret);
}