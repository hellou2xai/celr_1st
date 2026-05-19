-- WINEZONE Demo schema (Postgres translation of the Microsoft RMS tables
-- used by the analytics layer). Designed for COPY-friendly bulk seed.

DROP TABLE IF EXISTS tender_entry              CASCADE;
DROP TABLE IF EXISTS transaction_entry         CASCADE;
DROP TABLE IF EXISTS "transaction"             CASCADE;
DROP TABLE IF EXISTS purchase_order_entry      CASCADE;
DROP TABLE IF EXISTS purchase_order            CASCADE;
DROP TABLE IF EXISTS item_value_log            CASCADE;
DROP TABLE IF EXISTS non_tender_transaction    CASCADE;
DROP TABLE IF EXISTS drop_payout               CASCADE;
DROP TABLE IF EXISTS time_card                 CASCADE;
DROP TABLE IF EXISTS item                      CASCADE;
DROP TABLE IF EXISTS supplier                  CASCADE;
DROP TABLE IF EXISTS category                  CASCADE;
DROP TABLE IF EXISTS department                CASCADE;
DROP TABLE IF EXISTS customer                  CASCADE;
DROP TABLE IF EXISTS cashier                   CASCADE;
DROP TABLE IF EXISTS tender                    CASCADE;
DROP TABLE IF EXISTS reason_code               CASCADE;
DROP TABLE IF EXISTS batch                     CASCADE;
DROP TABLE IF EXISTS seed_marker               CASCADE;

CREATE TABLE department (
    id   INTEGER PRIMARY KEY,
    name TEXT
);

CREATE TABLE category (
    id   INTEGER PRIMARY KEY,
    name TEXT
);

CREATE TABLE supplier (
    id            INTEGER PRIMARY KEY,
    supplier_name TEXT
);

CREATE TABLE item (
    id                  INTEGER PRIMARY KEY,
    item_lookup_code    TEXT,
    description         TEXT,
    department_id       INTEGER REFERENCES department(id),
    category_id         INTEGER REFERENCES category(id),
    supplier_id         INTEGER REFERENCES supplier(id),
    bin_location        TEXT,
    quantity            NUMERIC(18,3) DEFAULT 0,
    quantity_committed  NUMERIC(18,3) DEFAULT 0,
    reorder_point       NUMERIC(18,3) DEFAULT 0,
    restock_level       NUMERIC(18,3) DEFAULT 0,
    cost                NUMERIC(18,4) DEFAULT 0,
    price               NUMERIC(18,4) DEFAULT 0,
    last_received       TIMESTAMP,
    last_sold           TIMESTAMP,
    last_counted        TIMESTAMP,
    last_updated        TIMESTAMP,
    inactive            INTEGER DEFAULT 0,
    taxable             INTEGER DEFAULT 1,
    date_created        TIMESTAMP
);
CREATE INDEX item_lookup_idx ON item (item_lookup_code);
CREATE INDEX item_desc_idx   ON item USING gin (to_tsvector('simple', description));
CREATE INDEX item_dept_idx   ON item (department_id);
CREATE INDEX item_supp_idx   ON item (supplier_id);

CREATE TABLE customer (
    id              INTEGER PRIMARY KEY,
    account_number  TEXT,
    title           TEXT,
    first_name      TEXT,
    last_name       TEXT,
    company         TEXT,
    email_address   TEXT,
    phone_number    TEXT,
    address         TEXT,
    city            TEXT,
    state           TEXT,
    zip             TEXT,
    account_opened  TIMESTAMP,
    last_visit      TIMESTAMP,
    total_visits    INTEGER DEFAULT 0,
    total_sales     NUMERIC(18,2) DEFAULT 0,
    total_savings   NUMERIC(18,2) DEFAULT 0,
    account_balance NUMERIC(18,2) DEFAULT 0,
    credit_limit    NUMERIC(18,2) DEFAULT 0,
    current_discount NUMERIC(9,4) DEFAULT 0,
    price_level     INTEGER DEFAULT 0,
    tax_exempt      INTEGER DEFAULT 0,
    employee        INTEGER DEFAULT 0,
    notes           TEXT
);
CREATE INDEX customer_name_idx ON customer (last_name, first_name);
CREATE INDEX customer_company_idx ON customer (company);

CREATE TABLE cashier (
    id              INTEGER PRIMARY KEY,
    name            TEXT,
    number          TEXT,
    inactive        INTEGER DEFAULT 0,
    return_limit    NUMERIC(18,2) DEFAULT 0,
    floor_limit     NUMERIC(18,2) DEFAULT 0,
    security_level  INTEGER DEFAULT 0
);

CREATE TABLE tender (
    id          INTEGER PRIMARY KEY,
    description TEXT,
    code        TEXT
);

CREATE TABLE reason_code (
    id          INTEGER PRIMARY KEY,
    description TEXT
);

CREATE TABLE batch (
    batch_number BIGINT PRIMARY KEY,
    opened       TIMESTAMP,
    closed       TIMESTAMP
);

CREATE TABLE "transaction" (
    transaction_number BIGINT PRIMARY KEY,
    batch_number       BIGINT,
    store_id           INTEGER DEFAULT 1,
    time               TIMESTAMP NOT NULL,
    customer_id        INTEGER,
    cashier_id         INTEGER,
    total              NUMERIC(18,2) DEFAULT 0,
    sales_tax          NUMERIC(18,2) DEFAULT 0,
    status             INTEGER DEFAULT 0,
    comment            TEXT,
    reference_number   TEXT
);
CREATE INDEX transaction_time_idx     ON "transaction" (time);
CREATE INDEX transaction_customer_idx ON "transaction" (customer_id);
CREATE INDEX transaction_cashier_idx  ON "transaction" (cashier_id);
CREATE INDEX transaction_time_brin    ON "transaction" USING brin (time);

CREATE TABLE transaction_entry (
    id                  BIGSERIAL PRIMARY KEY,
    transaction_number  BIGINT NOT NULL,
    item_id             INTEGER NOT NULL,
    quantity            NUMERIC(18,3) NOT NULL,
    price               NUMERIC(18,4) NOT NULL,
    full_price          NUMERIC(18,4) NOT NULL,
    cost                NUMERIC(18,4) NOT NULL,
    sales_tax           NUMERIC(18,4) DEFAULT 0,
    transaction_time    TIMESTAMP NOT NULL,
    store_id            INTEGER DEFAULT 1
);
CREATE INDEX te_txn_idx       ON transaction_entry (transaction_number);
CREATE INDEX te_item_idx      ON transaction_entry (item_id);
CREATE INDEX te_time_idx      ON transaction_entry (transaction_time);
CREATE INDEX te_time_brin     ON transaction_entry USING brin (transaction_time);
CREATE INDEX te_item_time_idx ON transaction_entry (item_id, transaction_time);

CREATE TABLE tender_entry (
    id                  BIGSERIAL PRIMARY KEY,
    transaction_number  BIGINT NOT NULL,
    tender_id           INTEGER NOT NULL REFERENCES tender(id),
    amount              NUMERIC(18,2) NOT NULL,
    time                TIMESTAMP NOT NULL
);
CREATE INDEX tender_entry_txn_idx  ON tender_entry (transaction_number);
CREATE INDEX tender_entry_time_idx ON tender_entry (time);

CREATE TABLE purchase_order (
    id            INTEGER PRIMARY KEY,
    po_number     TEXT,
    supplier_id   INTEGER REFERENCES supplier(id),
    status        INTEGER DEFAULT 0,
    date_created  TIMESTAMP,
    date_placed   TIMESTAMP,
    required_date TIMESTAMP
);
CREATE INDEX po_supplier_idx ON purchase_order (supplier_id);
CREATE INDEX po_created_idx  ON purchase_order (date_created);

CREATE TABLE purchase_order_entry (
    id                  BIGSERIAL PRIMARY KEY,
    purchase_order_id   INTEGER NOT NULL REFERENCES purchase_order(id),
    item_id             INTEGER NOT NULL,
    quantity_ordered    NUMERIC(18,3) DEFAULT 0,
    quantity_received   NUMERIC(18,3) DEFAULT 0,
    price               NUMERIC(18,4) DEFAULT 0,
    last_received_date  TIMESTAMP
);
CREATE INDEX poe_po_idx   ON purchase_order_entry (purchase_order_id);
CREATE INDEX poe_item_idx ON purchase_order_entry (item_id);

CREATE TABLE item_value_log (
    id           BIGSERIAL PRIMARY KEY,
    item_id      INTEGER NOT NULL,
    last_updated TIMESTAMP NOT NULL,
    amount_type  CHAR(1) NOT NULL,
    old_amount   NUMERIC(18,4),
    new_amount   NUMERIC(18,4)
);
CREATE INDEX ivl_item_idx ON item_value_log (item_id);
CREATE INDEX ivl_time_idx ON item_value_log (last_updated);

CREATE TABLE non_tender_transaction (
    id               BIGSERIAL PRIMARY KEY,
    cashier_id       INTEGER,
    transaction_type INTEGER,
    time             TIMESTAMP
);
CREATE INDEX ntt_time_idx ON non_tender_transaction (time);

CREATE TABLE drop_payout (
    id              BIGSERIAL PRIMARY KEY,
    cashier_id      INTEGER,
    time            TIMESTAMP,
    amount          NUMERIC(18,2),
    recipient       TEXT,
    comment         TEXT,
    reason_code_id  INTEGER
);

CREATE TABLE time_card (
    id          BIGSERIAL PRIMARY KEY,
    cashier_id  INTEGER,
    time_in     TIMESTAMP,
    time_out    TIMESTAMP,
    hours       NUMERIC(9,2)
);

-- Tracks whether the synthetic seed has already run on this database, so
-- redeploys do not re-seed. Render swap-deploys reuse the disk and DB.
CREATE TABLE seed_marker (
    id            INTEGER PRIMARY KEY DEFAULT 1,
    seeded_at     TIMESTAMP,
    seed_version  TEXT,
    txn_count     BIGINT,
    CHECK (id = 1)
);
