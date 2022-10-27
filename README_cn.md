Django ClickHouse Database Backend
===

简介
---

ClickHouse 数据库的 Django 数据库底端，实现使用Django原生的ORM操作clickhouse数据库。

底层驱动使用 [clickhouse-driver](https://clickhouse-driver.readthedocs.io/en/latest/) ，支持django 3.2及以上。
使用 [clickhouse-pool](https://github.com/ericmccarthy7/clickhouse-pool) 实现数据库连接池。

特性
---

支持以下功能：

- Migration: 支持数据库表的创建操作(CreateModel)和字段修改操作(AlterField)，能够使用makemigration和migrate命令创建表。

- Model: 支持定义ClickHouse特有的数据库属性：ENGINE, ORDER BY, PRIMARY KEY, PARTITION BY, Index。

- Test: 支持测试数据库创建和测试表创建，支持内置的TestCase和pytest-django

- QuerySet: 适配常见的CURD操作。

- Field: 支持常见的基本类型字段。

- 支持 Clickhouse 查询时设置项，[SETTINGS in SELECT Query](https://clickhouse.com/docs/en/sql-reference/statements/select/#settings-in-select) 。

快速上手
---

### 安装

```shell
pip install git+https://github.com/jayvynl/django-clickhouse-backend
```

### 使用

参考[示例项目](example)

#### 数据库设置

  以下例子中展示了PostgreSQL和ClickHouse双数据库的配置，其中ClickHouse只有`ENGINE`是必选项，其他项的默认值如下：
  
  - NAME: 默认数据库名称default
  - HOST: 默认连接地址localhost
  - PORT: 默认端口9000
  - USER: 默认用户default
  - PASSWORD: 默认密码为空

  ```python
  DATABASES = {
      'default': {
          'ENGINE': 'django.db.backends.postgresql',
          'NAME': 'test_project',
          'HOST': 'localhost',
          'USER': 'DB_USER',
          'PASSWORD': 'DB_PASSWORD'
      },
      'clickhouse': {
          'ENGINE': 'clickhouse_backend.backend',
          'NAME': 'default',
          'HOST': 'localhost',
          'USER': 'DB_USER',
          'PASSWORD': 'DB_PASSWORD',
          'TEST': {
              'fake_transaction': True
          }
      }
  }
  ```

#### 定义数据库模型

  支持ENGINE、ORDER BY、PARTITION BY等ClickHouse常用的属性，参考[示例项目](example/testapp/models.py)。
  
  `GenericIPAddressField` 建议使用 `clickhouse_backend.models.fields.GenericIPAddressField`，否则修改带IP类型的对象在保存时会报错。


#### 多数据库配置

  [多数据库配置](https://docs.djangoproject.com/en/3.2/topics/db/multi-db/) 允许让django根据对象自动选择操作的数据库。
  
  例如以下的配置让django自动将针对event这个app的所有数据库操作路由到clickhouse数据库。
  
  ```python
  class ClickHouseRouter:
      route_app_labels = {'event'}
      
      def db_for_read(self, model, **hints):
          if model._meta.app_label in self.route_app_labels:
              return 'clickhouse'
          return None
      
      def db_for_write(self, model, **hints):
          if model._meta.app_label in self.route_app_labels:
              return 'clickhouse'
          return None
      
      def allow_migrate(self, db, app_label, model_name=None, **hints):
          if app_label in self.route_app_labels:
              return db == 'clickhouse'
          elif db == 'clickhouse':
              return False
          return None
  ```
  
  然后在项目的配置文件中设置：
  
  ```python
  DATABASE_ROUTERS = ['test_project.dbrouter.ClickHouseRouter']
  ```

#### 数据库迁移

  ```shell
  python manage.py makemigrations
  python manage.py migrate --database clickhouse
  ```
  
  注意迁移的时候必须指定 `--database clickhouse` 指定执行clickhouse的迁移，否则默认执行default数据库的迁移。

#### 单元测试

  如果使用django内置的TestCase，需要为测试的类增加一个databases类属性，指定在测试中使用clickhouse数据库，例如：
  ```python
  from django.test import TestCase
  class Test(TestCase):
      databases = {'default', 'clickhouse_backend'}
  ```
  
  如果使用pytest和pytest-django，[多数据库测试](https://pytest-django.readthedocs.io/en/latest/database.html#tests-requiring-multiple-databases) 都需要为pytest.mark.django_db增加一个databases参数，指定在测试中使用clickhouse数据库。
  
  ```python
  import pytest
  from testapp.models import Event

  @pytest.mark.django_db(databases={'default', 'clickhouse_backend'})
  class Test:
      def test_spam(self):
          assert Event.objects.using('clickhouse').count() == 0
  ```
  
  > **注意**
  > 多数据库时，如果另一个数据库支持事务，使用 TransactionTestCase 或继承的类（包括 pytest_django）进行测试，每个数据库的所有测试数据（包括各种setup和pytest fixture）会在每个测试用例执行后自动清空（调用django的flush）。
  > 为了使用事务隔离各个测试用例的 postgresql 数据，需要所有数据库都支持事务，可以让 clickhouse 连接支持假事务，通过设置数据库里的 'TEST': {'fake_transaction': True}，参考[数据库设置](#数据库设置)。
  > 但是这会有个副作用，那就是各个测试用例的 clickhouse 数据会不隔离。所以一般情况不建议使用这个特性，除非你非常清楚这会带来什么影响。

其他说明
---

### 数据库迁移

数据库迁移只支持表初始的创建、表名修改、字段增删改等简单修改，那么如何维护其他的表结构更新呢?

目前没有好的办，假如没有生成正确的迁移文件，那么就需要手写迁移文件。

### 主键

Django要求每个数据库对象必须拥有唯一主键，但是ClickHouse中的主键含义和关系型数据库中的主键含义完全不同，而且也不要求主键是唯一的。

Django自动生成的主键是BigAutoField或AutoField，因为Django内置的model都使用了自动生成的主键，所以无可避免地要使用代码生成唯一主键。

- 使用AutoField

  在数据库中生成Int32类型的列，插入数据时需要手动指定主键值并确保唯一。

- 使用BigAutoField

  在数据库中生成Int64类型的列，插入数据时如果未指定主键值，那么默认会使用`clickhouse.idworker.id_worker`生成唯一主键。

  项目中用到了Twitter的snowflake算法生成唯一主键，实现在`clickhouse.idworker.snowflake.SnowflakeIDWorker`，如果使用多进程启动项目，必须保证每个进程的(CLICKHOUSE_WORKER_ID, CLICKHOUSE_DATACENTER_ID)环境变量是唯一的。
  
  因为使用work_id和datacenter_id都是5bit，所以范围是 0-31，如果传入了无效的值会报错，CLICKHOUSE_WORKER_ID默认值是0，CLICKHOUSE_DATACENTER_ID如果未提供则随即生成。

  出于效率，默认的`clickhouse.idworker.snowflake.SnowflakeIDWorker`是线程不安全的，用户可继承`clickhouse.idworker.base.BaseIDWorker`实现自己的版本，并在项目的`settings.py`中设置`CLICKHOUSE_ID_WORKER`值为自定义`BaseIDWorker`实例的倒入路径。

在Django 3.12，django内置的app或其他第三方app如果要使用BigAutoField作为默认主键类型，需要设置：

```python
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
```

### 查询时设置项

[SETTINGS in SELECT Query](https://clickhouse.com/docs/en/sql-reference/statements/select/#settings-in-select)

例如通过设置 `mutations_sync=1` 能够让数据的更新同步执行，默认情况下数据的修改是在后台异步执行的，参考 [mutations_sync](https://clickhouse.com/docs/en/operations/settings/settings/#mutations_sync) ：

```python
from testapp.models import Event
Event.objects.filter(protocol='S7').setting(mutations_sync=1).update(dst_port=102)
```

待实现
---

还有很多非常重要的特性待实现：

- 数据库的创建还有一些功能没有做，特有的SQL查询没有做。

- 特有的函数没有类封装。

- 数据库的修改没能支持所有类型。
