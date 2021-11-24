import React, { useEffect, useState } from "react";

const App = () => {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    const fetchStatus = async () => {
      const res = await fetch(`${process.env.BASE_SERVER_URL}/api/status`);
      const { message } = await res.json();

      setStatus(message);
    };

    fetchStatus();
  }, []);

  return (
    <>
      <h1>Hello world React!</h1>
      {status && <h2>And our server says: {status}</h2>}
    </>
  );
};

export default App;
