CREATE DATABASE crypto;
use crypto;

CREATE TABLE prices (
  name VARCHAR(20),
  price DECIMAL(19,4),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP 
);
