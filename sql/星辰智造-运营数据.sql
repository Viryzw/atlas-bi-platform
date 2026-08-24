-- Atlas BI 单企业运营测试库（MySQL 8.0+）
-- 企业名称：星辰智造有限公司
-- 数据库名称：xingchen_manufacturing
-- 注意：下面的 DROP TABLE / DROP VIEW 仅用于重建此测试库中的样例对象。

CREATE DATABASE IF NOT EXISTS `xingchen_manufacturing`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

USE `xingchen_manufacturing`;

DROP VIEW IF EXISTS `v_monthly_target_achievement`;
DROP VIEW IF EXISTS `v_monthly_performance`;
DROP TABLE IF EXISTS `inventory_snapshot`;
DROP TABLE IF EXISTS `sales_targets`;
DROP TABLE IF EXISTS `monthly_expenses`;
DROP TABLE IF EXISTS `operation_orders`;

-- 核心经营宽事实表：驾驶舱和绝大多数自然语言问数优先使用本表。
CREATE TABLE `operation_orders` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '订单记录主键',
  `order_no` VARCHAR(32) NOT NULL COMMENT '业务订单号',
  `order_date` DATE NOT NULL COMMENT '下单日期',
  `paid_at` DATETIME NULL COMMENT '支付时间',
  `completed_at` DATETIME NULL COMMENT '订单完成时间',
  `customer_name` VARCHAR(100) NOT NULL COMMENT '客户企业名称',
  `customer_type` ENUM('新客户','老客户','战略客户') NOT NULL COMMENT '客户类型',
  `region` VARCHAR(30) NOT NULL COMMENT '销售区域',
  `sales_department` VARCHAR(50) NOT NULL COMMENT '销售部门',
  `salesperson` VARCHAR(50) NOT NULL COMMENT '销售负责人',
  `product_category` VARCHAR(50) NOT NULL COMMENT '产品分类',
  `product_name` VARCHAR(100) NOT NULL COMMENT '产品名称',
  `quantity` INT UNSIGNED NOT NULL COMMENT '销售数量',
  `unit_price` DECIMAL(14,2) NOT NULL COMMENT '含税单价（元）',
  `gross_amount` DECIMAL(16,2) NOT NULL COMMENT '折扣前金额（元）',
  `discount_amount` DECIMAL(16,2) NOT NULL DEFAULT 0 COMMENT '折扣金额（元）',
  `sales_amount` DECIMAL(16,2) NOT NULL COMMENT '折后订单金额（元）',
  `cost_amount` DECIMAL(16,2) NOT NULL COMMENT '订单成本（元）',
  `received_amount` DECIMAL(16,2) NOT NULL DEFAULT 0 COMMENT '累计回款金额（元）',
  `refund_amount` DECIMAL(16,2) NOT NULL DEFAULT 0 COMMENT '退款金额（元）',
  `status` ENUM('pending','paid','completed','cancelled','refunded') NOT NULL COMMENT '订单状态',
  `payment_status` ENUM('unpaid','partial','paid','refunded') NOT NULL COMMENT '回款状态',
  `delivery_status` ENUM('pending','shipped','delivered','returned','cancelled') NOT NULL COMMENT '交付状态',
  `promised_delivery_date` DATE NULL COMMENT '承诺交付日期',
  `actual_delivery_date` DATE NULL COMMENT '实际交付日期',
  `is_new_customer` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否本期新增客户',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_operation_orders_order_no` (`order_no`),
  KEY `idx_operation_orders_date` (`order_date`),
  KEY `idx_operation_orders_customer` (`customer_name`),
  KEY `idx_operation_orders_region` (`region`),
  KEY `idx_operation_orders_status` (`status`),
  KEY `idx_operation_orders_department` (`sales_department`),
  CONSTRAINT `ck_operation_orders_quantity` CHECK (`quantity` > 0),
  CONSTRAINT `ck_operation_orders_amount` CHECK (
    `gross_amount` >= 0 AND `discount_amount` >= 0
    AND `sales_amount` >= 0 AND `cost_amount` >= 0
    AND `received_amount` >= 0 AND `refund_amount` >= 0
  ),
  CONSTRAINT `ck_operation_orders_sales_amount` CHECK (
    ABS(`sales_amount` - (`gross_amount` - `discount_amount`)) < 0.01
  )
) ENGINE=InnoDB COMMENT='星辰智造订单经营宽事实表';

CREATE TABLE `monthly_expenses` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `expense_month` DATE NOT NULL COMMENT '费用月份，统一为当月1日',
  `department_name` VARCHAR(50) NOT NULL COMMENT '费用承担部门',
  `expense_category` VARCHAR(50) NOT NULL COMMENT '费用类别',
  `expense_amount` DECIMAL(16,2) NOT NULL COMMENT '费用金额（元）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_monthly_expense` (`expense_month`,`department_name`,`expense_category`),
  KEY `idx_monthly_expenses_month` (`expense_month`)
) ENGINE=InnoDB COMMENT='月度期间费用';

CREATE TABLE `sales_targets` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `target_month` DATE NOT NULL COMMENT '目标月份，统一为当月1日',
  `sales_department` VARCHAR(50) NOT NULL COMMENT '销售部门',
  `target_sales_amount` DECIMAL(16,2) NOT NULL COMMENT '销售额目标（元）',
  `target_gross_margin_rate` DECIMAL(8,4) NOT NULL COMMENT '目标毛利率，如0.30表示30%',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_sales_target` (`target_month`,`sales_department`)
) ENGINE=InnoDB COMMENT='月度销售目标';

CREATE TABLE `inventory_snapshot` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `snapshot_date` DATE NOT NULL COMMENT '库存快照日期',
  `product_category` VARCHAR(50) NOT NULL,
  `product_name` VARCHAR(100) NOT NULL,
  `warehouse_name` VARCHAR(50) NOT NULL,
  `stock_quantity` INT UNSIGNED NOT NULL,
  `unit_cost` DECIMAL(14,2) NOT NULL,
  `safety_stock_quantity` INT UNSIGNED NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_inventory_snapshot` (`snapshot_date`,`product_name`,`warehouse_name`),
  KEY `idx_inventory_snapshot_date` (`snapshot_date`)
) ENGINE=InnoDB COMMENT='产品库存日快照';

DELIMITER $$

DROP PROCEDURE IF EXISTS `seed_xingchen_operations`$$
CREATE PROCEDURE `seed_xingchen_operations`()
BEGIN
  DECLARE i INT DEFAULT 1;
  DECLARE m INT DEFAULT 0;
  DECLARE v_order_date DATE;
  DECLARE v_status VARCHAR(20);
  DECLARE v_quantity INT;
  DECLARE v_unit_price DECIMAL(14,2);
  DECLARE v_gross DECIMAL(16,2);
  DECLARE v_discount DECIMAL(16,2);
  DECLARE v_sales DECIMAL(16,2);
  DECLARE v_cost DECIMAL(16,2);
  DECLARE v_refund DECIMAL(16,2);

  -- 生成 240 条覆盖 2025-09 至 2026-08 的确定性订单数据。
  WHILE i <= 240 DO
    SET v_order_date = DATE_ADD('2025-09-01', INTERVAL MOD(i * 17, 350) DAY);
    SET v_status = CASE
      WHEN MOD(i, 20) = 0 THEN 'cancelled'
      WHEN MOD(i, 20) = 17 THEN 'refunded'
      WHEN MOD(i, 20) = 19 THEN 'pending'
      WHEN MOD(i, 3) = 0 THEN 'paid'
      ELSE 'completed'
    END;
    SET v_quantity = 2 + MOD(i * 7, 18);
    SET v_unit_price = CASE MOD(i, 4)
      WHEN 0 THEN 6800.00
      WHEN 1 THEN 12800.00
      WHEN 2 THEN 19800.00
      ELSE 35800.00
    END;
    SET v_gross = ROUND(v_quantity * v_unit_price, 2);
    SET v_discount = ROUND(v_gross * CASE MOD(i, 5)
      WHEN 0 THEN 0.08 WHEN 1 THEN 0.05 ELSE 0.02 END, 2);
    SET v_sales = v_gross - v_discount;
    SET v_cost = ROUND(v_sales * (0.57 + MOD(i, 7) * 0.015), 2);
    SET v_refund = IF(v_status = 'refunded', ROUND(v_sales * 0.80, 2), 0);

    INSERT INTO `operation_orders` (
      `order_no`,`order_date`,`paid_at`,`completed_at`,
      `customer_name`,`customer_type`,`region`,`sales_department`,`salesperson`,
      `product_category`,`product_name`,`quantity`,`unit_price`,`gross_amount`,
      `discount_amount`,`sales_amount`,`cost_amount`,`received_amount`,`refund_amount`,
      `status`,`payment_status`,`delivery_status`,`promised_delivery_date`,
      `actual_delivery_date`,`is_new_customer`
    ) VALUES (
      CONCAT('XC', DATE_FORMAT(v_order_date, '%Y%m%d'), LPAD(i, 4, '0')),
      v_order_date,
      IF(v_status IN ('paid','completed','refunded'), TIMESTAMP(v_order_date, '10:00:00'), NULL),
      IF(v_status IN ('completed','refunded'), TIMESTAMP(DATE_ADD(v_order_date, INTERVAL 8 + MOD(i, 6) DAY), '16:00:00'), NULL),
      CASE MOD(i, 12)
        WHEN 0 THEN '远航科技有限公司' WHEN 1 THEN '华北装备集团'
        WHEN 2 THEN '云川自动化有限公司' WHEN 3 THEN '启明能源股份有限公司'
        WHEN 4 THEN '江南精工有限公司' WHEN 5 THEN '海岳电子有限公司'
        WHEN 6 THEN '北辰物流装备有限公司' WHEN 7 THEN '岭南智能科技有限公司'
        WHEN 8 THEN '瀚海新材料有限公司' WHEN 9 THEN '中原机械制造有限公司'
        WHEN 10 THEN '西部工业系统有限公司' ELSE '东方机器人有限公司'
      END,
      CASE WHEN i <= 12 OR MOD(i, 37) = 0 THEN '新客户'
           WHEN MOD(i, 6) = 0 THEN '战略客户' ELSE '老客户' END,
      CASE MOD(i, 4) WHEN 0 THEN '华东' WHEN 1 THEN '华南' WHEN 2 THEN '华北' ELSE '西部' END,
      CASE MOD(i, 3) WHEN 0 THEN '行业客户部' WHEN 1 THEN '渠道销售部' ELSE '战略客户部' END,
      CASE MOD(i, 6) WHEN 0 THEN '陈晨' WHEN 1 THEN '林涛' WHEN 2 THEN '王琳'
           WHEN 3 THEN '赵凯' WHEN 4 THEN '周敏' ELSE '刘洋' END,
      CASE MOD(i, 4) WHEN 0 THEN '工业机器人' WHEN 1 THEN '智能传感器'
           WHEN 2 THEN '控制系统' ELSE '自动化产线' END,
      CASE MOD(i, 4) WHEN 0 THEN 'XC-R6 六轴机器人' WHEN 1 THEN 'XC-S20 智能传感器'
           WHEN 2 THEN 'XC-C8 运动控制器' ELSE 'XC-L2 柔性装配线' END,
      v_quantity,
      v_unit_price,
      v_gross,
      v_discount,
      v_sales,
      v_cost,
      CASE
        WHEN v_status IN ('paid','completed') THEN v_sales
        WHEN v_status = 'refunded' THEN v_sales - v_refund
        ELSE 0
      END,
      v_refund,
      v_status,
      CASE WHEN v_status = 'cancelled' OR v_status = 'pending' THEN 'unpaid'
           WHEN v_status = 'refunded' THEN 'refunded' ELSE 'paid' END,
      CASE WHEN v_status = 'cancelled' THEN 'cancelled'
           WHEN v_status = 'pending' THEN 'pending'
           WHEN v_status = 'paid' THEN 'shipped'
           WHEN v_status = 'refunded' THEN 'returned' ELSE 'delivered' END,
      DATE_ADD(v_order_date, INTERVAL 12 DAY),
      IF(v_status IN ('completed','refunded'), DATE_ADD(v_order_date, INTERVAL 8 + MOD(i, 7) DAY), NULL),
      IF(i <= 12 OR MOD(i, 37) = 0, 1, 0)
    );
    SET i = i + 1;
  END WHILE;

  -- 生成 12 个月的部门目标和费用。
  WHILE m < 12 DO
    INSERT INTO `sales_targets`
      (`target_month`,`sales_department`,`target_sales_amount`,`target_gross_margin_rate`)
    VALUES
      (DATE_ADD('2025-09-01', INTERVAL m MONTH), '行业客户部', 1200000 + m * 35000, 0.30),
      (DATE_ADD('2025-09-01', INTERVAL m MONTH), '渠道销售部', 1000000 + m * 30000, 0.28),
      (DATE_ADD('2025-09-01', INTERVAL m MONTH), '战略客户部', 1500000 + m * 45000, 0.32);

    INSERT INTO `monthly_expenses`
      (`expense_month`,`department_name`,`expense_category`,`expense_amount`)
    VALUES
      (DATE_ADD('2025-09-01', INTERVAL m MONTH), '销售中心', '销售费用', 165000 + m * 3500),
      (DATE_ADD('2025-09-01', INTERVAL m MONTH), '研发中心', '研发费用', 280000 + m * 5000),
      (DATE_ADD('2025-09-01', INTERVAL m MONTH), '管理中心', '管理费用', 135000 + m * 2500),
      (DATE_ADD('2025-09-01', INTERVAL m MONTH), '运营中心', '仓储物流费', 95000 + m * 2200);
    SET m = m + 1;
  END WHILE;
END$$

CALL `seed_xingchen_operations`()$$
DROP PROCEDURE `seed_xingchen_operations`$$

DELIMITER ;

INSERT INTO `inventory_snapshot`
  (`snapshot_date`,`product_category`,`product_name`,`warehouse_name`,`stock_quantity`,`unit_cost`,`safety_stock_quantity`)
VALUES
  ('2026-08-18','工业机器人','XC-R6 六轴机器人','上海中心仓',38,21800.00,25),
  ('2026-08-18','智能传感器','XC-S20 智能传感器','上海中心仓',420,3900.00,280),
  ('2026-08-18','控制系统','XC-C8 运动控制器','上海中心仓',135,11600.00,100),
  ('2026-08-18','自动化产线','XC-L2 柔性装配线','上海中心仓',12,112000.00,8),
  ('2026-08-18','工业机器人','XC-R6 六轴机器人','广州区域仓',16,21800.00,18),
  ('2026-08-18','智能传感器','XC-S20 智能传感器','广州区域仓',180,3900.00,160),
  ('2026-08-18','控制系统','XC-C8 运动控制器','成都区域仓',72,11600.00,80),
  ('2026-08-18','自动化产线','XC-L2 柔性装配线','成都区域仓',5,112000.00,6);

CREATE VIEW `v_monthly_performance` AS
SELECT
  CAST(DATE_FORMAT(`order_date`, '%Y-%m-01') AS DATE) AS `month_start`,
  `sales_department`,
  SUM(CASE WHEN `status` IN ('paid','completed') THEN `sales_amount` ELSE 0 END) AS `sales_amount`,
  SUM(CASE WHEN `status` IN ('paid','completed') THEN `sales_amount` - `cost_amount` ELSE 0 END) AS `gross_profit`,
  SUM(CASE WHEN `status` <> 'cancelled' THEN 1 ELSE 0 END) AS `valid_order_count`,
  COUNT(DISTINCT CASE WHEN `status` IN ('paid','completed') THEN `customer_name` END) AS `customer_count`,
  SUM(`received_amount`) AS `received_amount`,
  SUM(`refund_amount`) AS `refund_amount`,
  SUM(CASE WHEN `status` = 'completed' THEN 1 ELSE 0 END) AS `completed_order_count`,
  SUM(CASE WHEN `status` = 'completed' AND `actual_delivery_date` <= `promised_delivery_date` THEN 1 ELSE 0 END) AS `on_time_order_count`
FROM `operation_orders`
GROUP BY CAST(DATE_FORMAT(`order_date`, '%Y-%m-01') AS DATE), `sales_department`;

CREATE VIEW `v_monthly_target_achievement` AS
SELECT
  t.`target_month`,
  t.`sales_department`,
  t.`target_sales_amount`,
  t.`target_gross_margin_rate`,
  COALESCE(p.`sales_amount`, 0) AS `actual_sales_amount`,
  COALESCE(p.`gross_profit`, 0) AS `actual_gross_profit`,
  100.0 * COALESCE(p.`sales_amount`, 0) / NULLIF(t.`target_sales_amount`, 0) AS `target_achievement_rate`,
  100.0 * COALESCE(p.`gross_profit`, 0) / NULLIF(p.`sales_amount`, 0) AS `actual_gross_margin_rate`
FROM `sales_targets` t
LEFT JOIN `v_monthly_performance` p
  ON p.`month_start` = t.`target_month`
 AND p.`sales_department` = t.`sales_department`;

-- 只读数据库账号由 Atlas BI 后端统一创建和授权，SQL 文件无需携带账号或密码。

-- ============================================================
-- 数据校验：以下查询应全部正常返回。
-- ============================================================

-- 1. 表与视图是否齐全。
SELECT `TABLE_NAME`, `TABLE_TYPE`
FROM `information_schema`.`TABLES`
WHERE `TABLE_SCHEMA` = 'xingchen_manufacturing'
ORDER BY `TABLE_TYPE`, `TABLE_NAME`;

-- 2. 基础数据量与日期范围：预期订单240、费用48、目标36、库存8。
SELECT 'operation_orders' AS object_name, COUNT(*) AS row_count,
       MIN(`order_date`) AS min_date, MAX(`order_date`) AS max_date
FROM `operation_orders`
UNION ALL
SELECT 'monthly_expenses', COUNT(*), MIN(`expense_month`), MAX(`expense_month`) FROM `monthly_expenses`
UNION ALL
SELECT 'sales_targets', COUNT(*), MIN(`target_month`), MAX(`target_month`) FROM `sales_targets`
UNION ALL
SELECT 'inventory_snapshot', COUNT(*), MIN(`snapshot_date`), MAX(`snapshot_date`) FROM `inventory_snapshot`;

-- 3. 金额与日期质量：预期三项均为0。
SELECT
  SUM(ABS(`sales_amount` - (`gross_amount` - `discount_amount`)) >= 0.01) AS invalid_sales_amount,
  SUM(`received_amount` > `sales_amount`) AS invalid_received_amount,
  SUM(`actual_delivery_date` IS NOT NULL AND `actual_delivery_date` < `order_date`) AS invalid_delivery_date
FROM `operation_orders`;

-- 4. 核心 KPI 汇总。
SELECT
  SUM(CASE WHEN `status` IN ('paid','completed') THEN `sales_amount` ELSE 0 END) AS sales_amount,
  SUM(CASE WHEN `status` <> 'cancelled' THEN 1 ELSE 0 END) AS order_count,
  COUNT(DISTINCT CASE WHEN `status` IN ('paid','completed') THEN `customer_name` END) AS customer_count,
  ROUND(100.0 * SUM(`status` = 'completed') / NULLIF(SUM(`status` <> 'cancelled'), 0), 2) AS completion_rate,
  SUM(CASE WHEN `status` IN ('paid','completed') THEN `sales_amount` - `cost_amount` ELSE 0 END) AS gross_profit,
  ROUND(100.0 * SUM(CASE WHEN `status` IN ('paid','completed') THEN `sales_amount` - `cost_amount` ELSE 0 END)
    / NULLIF(SUM(CASE WHEN `status` IN ('paid','completed') THEN `sales_amount` ELSE 0 END), 0), 2) AS gross_margin_rate
FROM `operation_orders`;

-- 5. 月度趋势与区域分布。
SELECT DATE_FORMAT(`order_date`, '%Y-%m') AS month,
       SUM(CASE WHEN `status` IN ('paid','completed') THEN `sales_amount` ELSE 0 END) AS sales_amount
FROM `operation_orders`
GROUP BY DATE_FORMAT(`order_date`, '%Y-%m')
ORDER BY month;

SELECT `region`,
       SUM(CASE WHEN `status` IN ('paid','completed') THEN `sales_amount` ELSE 0 END) AS sales_amount
FROM `operation_orders`
GROUP BY `region`
ORDER BY sales_amount DESC;

-- 6. 目标达成、费用与库存校验。
SELECT * FROM `v_monthly_target_achievement`
ORDER BY `target_month`, `sales_department`;

SELECT `expense_month`, SUM(`expense_amount`) AS total_expense
FROM `monthly_expenses`
GROUP BY `expense_month`
ORDER BY `expense_month`;

SELECT `warehouse_name`,
       SUM(`stock_quantity` * `unit_cost`) AS inventory_value,
       SUM(`stock_quantity` < `safety_stock_quantity`) AS below_safety_sku_count
FROM `inventory_snapshot`
WHERE `snapshot_date` = (SELECT MAX(`snapshot_date`) FROM `inventory_snapshot`)
GROUP BY `warehouse_name`;
