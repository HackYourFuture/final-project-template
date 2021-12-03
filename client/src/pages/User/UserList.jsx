import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import useFetch from "../../hooks/useFetch";
import TEST_ID from "./UserList.testid";

const UserList = () => {
  const [users, setUsers] = useState(null);
  const { isLoading, error, performFetch, cancelFetch } = useFetch(
    "/user",
    (response) => {
      setUsers(response.result);
    }
  );

  useEffect(() => {
    performFetch();

    return cancelFetch;
  }, []);

  let content = null;

  if (isLoading) {
    content = <div data-testid={TEST_ID.loadingContainer}>loading...</div>;
  } else if (error != null) {
    content = (
      <div data-testid={TEST_ID.errorContainer}>Error: {error.toString()}</div>
    );
  } else {
    content = (
      <>
        <h1>These are the users</h1>
        <ul data-testid={TEST_ID.userList} data-loaded={users != null}>
          {users &&
            users.map((user) => {
              return (
                <li key={user._id} data-elementid={user._id}>
                  {user.name} ({user.email})
                </li>
              );
            })}
        </ul>
        <Link to="/user/create" data-testid={TEST_ID.createUserButton}>
          <button>Create new user</button>
        </Link>
      </>
    );
  }

  return <div data-testid={TEST_ID.container}>{content}</div>;
};

export default UserList;
