import Link from "next/link";
import { BACKEND_API_URL } from "@/lib/config";
import type { User } from "./types";

async function getUsers(): Promise<User[]> {
  const res = await fetch(`${BACKEND_API_URL}/api/users`, {
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error("Could not load users");
  }

  return res.json();
}

export default async function UsersPage() {
  let users: User[];

  try {
    users = await getUsers();
  } catch {
    return <p>Could not load users</p>;
  }

  if (users.length === 0) {
    return <p>No users found</p>;
  }

  return (
    <div>
      <h1>Users</h1>
      <ul>
        {users.map((user) => (
          <li key={user.id}>{user.email}</li>
        ))}
      </ul>
      <Link href="/">Back to home</Link>
    </div>
  );
}
