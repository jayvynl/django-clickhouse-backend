0.1.0 (2022-10-16)
---

- ID worker 接口变动以及配置项调整.
- 支持数据库连接池.
- 重构了 Engine 的实现，更加简洁稳定.
- 数据库相关特性集中在 SQLCompiler 实现.
- 忽略不支持的字段级别 db_index 属性，以及 AlterUniqueTogether 迁移操作，以支持django内置model或第三方model迁移.

0.0.14 (2022-08-18)
---

- 匹配 Django 4.x 。

0.0.13 (2022-08-18)
---

- 修复了搜索 GenericIPAddressField 字段。

0.0.12 (2022-08-09)
---

- 修复了创建表时，多个 order by 字段出错的问题。

0.0.11 (2022-08-01)
---

- 修复了 AlterField migration ，支持 Nullable 到非 Nullable 类型改变，使用提供的默认值更新旧的 `NULL` 值。

0.0.10
---

- 支持字段类型变化migration

0.0.9
---

- 修复删除、更新模型对象不能同步执行的问题

0.0.8
---

- QuerySet 支持 setting 查询，可用传入 Clickhouse 设置项，参考[SETTINGS in SELECT Query](https://clickhouse.com/docs/en/sql-reference/statements/select/#settings-in-select)
- 修复插入数据时不能设置正确的对象id，bulk_create 和 create 和 save 均能展示正确的id

0.0.7
---

- 数据库连接加入fake_transaction属性，测试时设置这个属性可以使postgresql等支持事物的其他数据库数据不清空
- 加入AutoField类型，映射到Int32
- 完善文档中关于测试/迁移/主键的说明

0.0.6
---

- 优化了GenericIPAddressField类型字段在存储ipv4地址时，默认输出类型为Ipv6格式，将其转换为对应的Ipv4类型

0.0.5
---

- 修复了clickhouse driver转义datetime类型值后，丢失时区的问题

0.0.4
---

- 新增PositiveSmallIntegerField, PositiveIntegerField, PositiveBigIntegerField字段类型，分别对应正确的clickhouse uint类型范围。

- 修改README，修正关于单元测试的说明。

0.0.3
---

- 解决了多app时，clickhouse.models 中 options.DEFAULT_NAMES monkey patch未生效的问题。

- 完善README，增加了自增主键的说明，调整了格式。
