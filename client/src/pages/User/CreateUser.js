import React, { useState } from "react";

import useFetch from "../../hooks/useFetch";

const CreateUser = () => {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");

  const onSuccess = () => {
    setName("");
    setEmail("");
  };
  const { isLoading, error, performFetch } = useFetch(
    "/user/create",
    onSuccess
  );

  const handleSubmit = (e) => {
    e.preventDefault();
    performFetch({
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify({ user: { name, email } }),
    });
  };

  let statusComponent = <></>;
  if (error != null) {
    statusComponent = (
      <>Error while trying to create user: {error.toString()}</>
    );
  } else if (isLoading) {
    statusComponent = <>Creating user....</>;
  }

  return (
    <>
      <h1>What should the user be?</h1>
      <form onSubmit={handleSubmit}>
        <input
          name="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          name="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <button type="submit">Submit</button>
      </form>
      {statusComponent}
    </>
  );
};

export default CreateUser;
