import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import useFetch from "../../hooks/useFetch";
import TEST_ID from "./UserList.testid";

const UserList = () => {
  const [users, setUsers] = useState([]);
  const { isLoading, error, performFetch } = useFetch("/user", (response) => {
    setUsers(response.result);
  });

  useEffect(performFetch, []);

  let content = null;

  if (isLoading) {
    content = <>loading...</>;
  }

  if (error != null) {
    content = <>Error: {error.toString()}</>;
  }

  content = (
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

  return <div data-testid={TEST_ID.container}>{content}</div>;
};

export default UserList;
