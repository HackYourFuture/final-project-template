/**
 * This file is used to clean up the filename you get from __filename to get rid of all the part of the filename until <your file system>/src
 */
const cleanFilename = (filename) => {
  const indexToCut = filename.lastIndexOf("/src/");

  return filename.slice(indexToCut);
};

export default cleanFilename;
