-- LOCAL only. A separate database for the automated tests, so `pnpm test:api` never touches
-- the development data.
CREATE DATABASE p2b_test;
