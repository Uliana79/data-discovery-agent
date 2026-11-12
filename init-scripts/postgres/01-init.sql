-- Таблица пользователей
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    full_name VARCHAR(255),
    age INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

INSERT INTO users (email, full_name, age) VALUES
('john@example.com', 'John Doe', 30),
('jane@example.com', 'Jane Smith', 25),
('bob@example.com', 'Bob Johnson', 40);

-- Таблица заказов
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    order_date TIMESTAMP DEFAULT NOW(),
    amount DECIMAL(10,2) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending'
);

INSERT INTO orders (user_id, amount, status) VALUES
(1, 150.50, 'completed'),
(1, 75.00, 'pending'),
(2, 200.00, 'completed');

-- Таблица продуктов
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    category VARCHAR(100),
    in_stock BOOLEAN DEFAULT TRUE
);

INSERT INTO products (name, price, category) VALUES
('Laptop', 999.99, 'Electronics'),
('Mouse', 25.50, 'Electronics'),
('Book', 15.99, 'Education');

-- Таблица платежей
CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    amount DECIMAL(10,2) NOT NULL,
    payment_date TIMESTAMP DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'pending',
    payment_method VARCHAR(50)
);

INSERT INTO payments (order_id, amount, status, payment_method) VALUES
(1, 150.50, 'completed', 'card'),
(1, 75.00, 'pending', 'cash'),
(2, 200.00, 'completed', 'card');

-- Таблица клиентов
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    contact_name VARCHAR(255),
    contact_email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(50),
    address TEXT,
    city VARCHAR(100),
    country VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    vat_number VARCHAR(50)
);

INSERT INTO customers (company_name, contact_name, contact_email, phone, address, city, country, vat_number) VALUES
('ООО Ромашка', 'Иван Петров', 'ivan@romashka.ru', '+7-495-111-22-33', 'ул. Цветочная, 15', 'Москва', 'Россия', 'RU123456789'),
('ИП Иванов', 'Сергей Иванов', 'sergey@ivanov.ru', '+7-495-222-33-44', 'пр. Мира, 10', 'Санкт-Петербург', 'Россия', 'RU987654321'),
('ЗАО Березка', 'Елена Смирнова', 'elena@berezka.ru', '+7-495-333-44-55', 'ул. Луговая, 25', 'Казань', 'Россия', 'RU456789123');