import { useState } from "react";

/**
 * Our useFetch hook should be used for all communication with the server.
 *
 * route - This is the route you want to access on the server. It should NOT include the /api part, so should be /user or /user/{id}
 * onReceived - a function that will be called with the response of the server. Will only be called if everything went well!
 *
 * Our hook will give you an object with the properties:
 *
 * isLoading - true if the fetch is still in progress
 * error - will contain an Error object if something went wrong
 * performFetch - this function will trigger the fetching. It is up to the user of the hook to determine when to do this!
 */
const useFetch = (route, onReceived) => {
  if (route.includes("api/")) {
    /**
     * We add this check here to provide a better error message if you accidentally add the api part
     * As an error that happens later because of this can be very confusing!
     */
    throw Error(
      "when using the useFetch hook, the route should not include the /api/ part"
    );
  }

  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  // Add any args given to the function to the fetch function
  const performFetch = (...args) => {
    setError(null);
    setIsLoading(true);

    const fetchUsers = async () => {
      // We add the /api subsection here to make it a single point of change if our configuration changes
      const url = `${process.env.BASE_SERVER_URL}/api${route}`;

      const res = await fetch(url, ...args);

      if (!res.ok) {
        setError(
          new Error(
            `Fetch for ${url} returned an invalid status (${
              res.status
            }). Received: ${JSON.stringify(res)}`
          )
        );
      }

      const jsonResult = await res.json();

      if (jsonResult.success === true) {
        onReceived(jsonResult);
      } else {
        setError(
          new Error(
            jsonResult.msg ||
              `The result from our API did not have an error message. Received: ${JSON.stringify(
                jsonResult
              )}`
          )
        );
      }

      setIsLoading(false);
    };

    try {
      fetchUsers();
    } catch (error) {
      setError(error);
    }
  };

  return { isLoading, error, performFetch };
};

export default useFetch;
