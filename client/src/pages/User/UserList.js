import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import useFetch from "../../hooks/useFetch";

const UserList = () => {
  const [users, setUsers] = useState([]);
  const { isLoading, error, performFetch } = useFetch("/user", (response) => {
    setUsers(response.result);
    console.log(response);
  });

  console.log("users", users);
  useEffect(performFetch, []);

  if (isLoading) {
    return <>loading...</>;
  }

  if (error != null) {
    console.error(error);
    return <>Error: {error.toString()}</>;
  }

  return (
    <>
      <h1>These are the users</h1>
      <ul>
        {users.map((user) => {
          return (
            <li key={user._id}>
              {user.name} ({user.email})
            </li>
          );
        })}
      </ul>
      <Link to="/user/create">
        <button>Create new user</button>
      </Link>
    </>
  );
};

export default UserList;
