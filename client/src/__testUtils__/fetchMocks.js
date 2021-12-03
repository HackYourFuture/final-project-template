export const asSlowResponse = (response) => {
  return () => new Promise((resolve) => setTimeout(() => resolve(response)));
};
