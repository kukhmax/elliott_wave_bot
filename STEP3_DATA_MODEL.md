# Шаг 3. Модель данных и настроек Elliott Bot

## 1. Цель шага

- Зафиксировать сущности, на которых будет строиться логика бота.
- Определить, какие данные нужны для мониторинга, анализа волн, сигналов и настроек.
- Разделить постоянное состояние, временное состояние и вычисляемые результаты.

## 2. Принципы модели данных

- Данные разделяются на пользовательские настройки, рыночные данные, аналитические результаты и служебное состояние.
- Постоянно хранятся только те сущности, которые нужны после перезапуска.
- Рыночные свечи считаются входными данными и по умолчанию не сохраняются навсегда.
- Аналитические результаты хранятся в том объеме, который нужен для антидублей, объяснения сигнала и отладки.
- Форматы должны одинаково работать для long и short сценариев.
- Все сущности должны быть пригодны для локального запуска и для запуска через Docker с внешним volume.

## 3. Основные доменные сущности

### 3.1 TradingPair

Назначение:

- Представлять торговый инструмент, доступный для проверки.

Поля:

- `symbol` — каноническое имя пары внутри приложения.
- `base_asset` — базовый актив.
- `quote_asset` — котируемый актив.
- `exchange` — источник свечей.
- `status` — активна ли пара для мониторинга.
- `source_origin` — откуда пара попала в систему: auto или manual.

Пример смысла:

- Пара нужна для watchlist, мониторинга и ручной проверки.

### 3.2 PairMonitoringConfig

Назначение:

- Хранить индивидуальные параметры мониторинга конкретной пары.

Поля:

- `symbol`
- `timeframe`
- `scan_enabled`
- `priority`
- `history_depth`
- `last_checked_at`
- `last_signal_at`
- `last_signal_signature`

Назначение хранения:

- Используется Monitoring Coordinator и Watchlist Service.

### 3.3 AppSettings

Назначение:

- Хранить глобальные настройки приложения.

Поля:

- `default_timeframe`
- `scan_interval_seconds`
- `default_history_depth`
- `max_pairs`
- `search_mode`
- `extremum_sensitivity`
- `auto_universe_enabled`
- `stablecoin_filter_enabled`
- `exchange`
- `notifications_enabled`
- `manual_check_explain_rejections`
- `storage_path`
- `environment`

Комментарий по смыслу:

- Эти настройки читаются при старте и могут обновляться пользователем через бота.
- `storage_path` должен быть совместим с внешним volume при запуске через Docker.

### 3.4 OHLCVBar

Назначение:

- Представлять одну свечу рынка в нормализованном виде.

Поля:

- `open_time`
- `close_time`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `symbol`
- `timeframe`

### 3.5 MarketSeries

Назначение:

- Представлять набор свечей для одного анализа.

Поля:

- `symbol`
- `timeframe`
- `bars`
- `loaded_at`
- `source`

### 3.6 ExtremumPoint

Назначение:

- Представлять локальный максимум или минимум.

Поля:

- `index`
- `timestamp`
- `price`
- `kind`
- `strength`
- `bar_distance_from_previous`

### 3.7 WavePointSet

Назначение:

- Представлять опорные точки P0-P5 для одного кандидата.

Поля:

- `p0`
- `p1`
- `p2`
- `p3`
- `p4`
- `p5`
- `direction`

### 3.8 WaveCandidate

Назначение:

- Представлять найденный кандидат на 5-волновую структуру до финальной валидации.

Поля:

- `candidate_id`
- `symbol`
- `timeframe`
- `direction`
- `points`
- `wave1_type`
- `wave2_type`
- `wave3_type`
- `wave4_type`
- `wave5_type`
- `length_wave1`
- `length_wave2`
- `length_wave3`
- `length_wave4`
- `length_wave5`
- `source_extremums`
- `generated_at`

### 3.9 ElliottValidationResult

Назначение:

- Представлять итог строгой проверки кандидата.

Поля:

- `candidate_id`
- `status`
- `confidence_score`
- `hard_rules_passed`
- `hard_rules_failed`
- `soft_rules_passed`
- `soft_rules_failed`
- `fibonacci_metrics`
- `alternation_summary`
- `diagnostic_summary`

Статусы:

- `confirmed`
- `probable`
- `rejected`

### 3.10 FinalSignal

Назначение:

- Представлять итоговый сигнал, готовый к отправке пользователю.

Поля:

- `signal_id`
- `symbol`
- `timeframe`
- `direction`
- `status`
- `points`
- `wave_summary`
- `rules_summary`
- `confidence_score`
- `chart_path`
- `created_at`

### 3.11 SignalRecord

Назначение:

- Хранить историю отправленных или подавленных сигналов.

Поля:

- `signal_id`
- `signal_signature`
- `symbol`
- `timeframe`
- `direction`
- `status`
- `sent_to_telegram`
- `duplicate_of`
- `created_at`
- `suppressed_reason`

Назначение хранения:

- Используется для антидублей и истории решений.

### 3.12 ManualCheckRequest

Назначение:

- Представлять разовый пользовательский запрос на анализ пары.

Поля:

- `request_id`
- `symbol`
- `timeframe`
- `requested_at`
- `requested_by`
- `explain_rejections`

### 3.13 ManualCheckResult

Назначение:

- Представлять ответ по ручной проверке.

Поля:

- `request_id`
- `symbol`
- `timeframe`
- `result_status`
- `best_candidate`
- `validation_result`
- `rejection_reason`
- `chart_path`
- `completed_at`

### 3.14 RuntimeState

Назначение:

- Хранить текущее служебное состояние бота в процессе работы.

Поля:

- `bot_status`
- `monitoring_status`
- `started_at`
- `current_cycle_started_at`
- `current_pair`
- `queue_size`
- `last_error`

Статусы:

- `idle`
- `running`
- `paused`
- `stopped`
- `error`

## 4. Что хранится постоянно

Постоянно сохраняются:

- `AppSettings`
- `TradingPair`
- `PairMonitoringConfig`
- `SignalRecord`
- Последнее актуальное `RuntimeState` в сокращенном виде

Необязательно сохраняются постоянно:

- `ManualCheckResult` — можно хранить ограниченно для истории.
- `FinalSignal` — можно восстанавливать из `SignalRecord`, если не требуется полный архив сообщений.

По умолчанию не сохраняются постоянно:

- `OHLCVBar`
- `MarketSeries`
- `ExtremumPoint`
- `WaveCandidate`

## 5. Что считается временными данными

- Загруженные свечи текущего цикла.
- Список экстремумов для конкретного анализа.
- Все промежуточные кандидаты до финального решения.
- Временные файлы графиков, если они не нужны как архив.

## 6. Связи между сущностями

- Один `TradingPair` связан с одной активной записью `PairMonitoringConfig`.
- Один `MarketSeries` содержит много `OHLCVBar`.
- Один `WaveCandidate` использует один `WavePointSet` и ссылается на много `ExtremumPoint`.
- Один `WaveCandidate` имеет один `ElliottValidationResult`.
- Один `ElliottValidationResult` может быть преобразован в один `FinalSignal`.
- Один `FinalSignal` записывается в один `SignalRecord`.
- Один `ManualCheckRequest` порождает один `ManualCheckResult`.

## 7. Правила поведения состояния при действиях пользователя

### 7.1 При нажатии Старт

- `monitoring_status` переходит в `running`.
- Если включен автонабор рынка, создаются или обновляются записи `TradingPair` и `PairMonitoringConfig`.
- Ранее сохраненные ручные пары не удаляются.
- Настройки загружаются из `AppSettings`.

### 7.2 При нажатии Стоп

- `monitoring_status` переходит в `paused` или `stopped`.
- Watchlist и настройки не удаляются.
- История сигналов не удаляется.
- Последнее состояние сохраняется для последующего продолжения работы.

### 7.3 При добавлении пары вручную

- Создается или активируется запись `TradingPair`.
- Создается или обновляется `PairMonitoringConfig`.
- `source_origin` помечается как `manual`.

### 7.4 При удалении пары

- Пара исключается из активного мониторинга.
- История ранее отправленных сигналов по ней сохраняется.

### 7.5 При ручной проверке

- Создается `ManualCheckRequest`.
- Запускается разовый анализ без обязательного добавления пары в watchlist.
- Возвращается `ManualCheckResult`.

## 8. Поддержка антидублей

Для антидублей нужен `signal_signature`, который строится из:

- `symbol`
- `timeframe`
- `direction`
- ключевых координат P0-P5
- статуса сценария

Если новая сигнатура совпадает с последней отправленной по той же паре и таймфрейму:

- уведомление не отправляется повторно;
- в `SignalRecord` сохраняется факт подавления как дубля.

## 9. Требования к конфигурации через окружение

Обязательные параметры окружения:

- `TELEGRAM_BOT_TOKEN`
- `MARKET_DATA_PROVIDER`
- `MARKET_UNIVERSE_PROVIDER`

Рекомендуемые параметры окружения:

- `DEFAULT_TIMEFRAME`
- `SCAN_INTERVAL_SECONDS`
- `DEFAULT_HISTORY_DEPTH`
- `EXCHANGE`
- `STORAGE_PATH`
- `LOG_LEVEL`

Архитектурное значение:

- Эти параметры должны одинаково работать локально и в Docker-контейнере.
- `STORAGE_PATH` должен указывать на директорию, пригодную для подключения как volume.

## 10. Минимальный формат хранения

На уровне проектирования допускаются два варианта:

- файловое хранение для первой версии;
- база данных для следующей итерации.

Для первой версии достаточно:

- `settings`
- `watchlist`
- `signal_history`
- `runtime_state`

## 11. Приоритет внедрения модели данных

1. `AppSettings`
2. `TradingPair`
3. `PairMonitoringConfig`
4. `OHLCVBar` и `MarketSeries`
5. `ExtremumPoint`
6. `WavePointSet`
7. `WaveCandidate`
8. `ElliottValidationResult`
9. `SignalRecord`
10. `RuntimeState`
11. `ManualCheckRequest` и `ManualCheckResult`

## 12. Результат шага 3

- Зафиксирована модель данных для мониторинга, анализа и уведомлений.
- Определено, какие сущности хранятся постоянно, а какие являются временными.
- Зафиксированы правила изменения состояния при Старт, Стоп, ручной проверке и управлении watchlist.
- Модель совместима с запуском через Docker за счет конфигурации через окружение и внешнего пути хранения.
