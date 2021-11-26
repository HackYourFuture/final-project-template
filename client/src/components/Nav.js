import React from "react";
import { Link } from "react-router-dom";

const Nav = () => {
  return (
    <ul>
      <Link to="/">
        <li>Home</li>
      </Link>
      <Link to="/user">
        <li>Users</li>
      </Link>
    </ul>
  );
};

export default Nav;
