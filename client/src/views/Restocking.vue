<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error && !successOrder" class="error">{{ error }}</div>
    <div v-else>
      <div v-if="successOrder" class="success-banner">
        <span>{{ t('restocking.orderSuccess', { orderNumber: successOrder.order_number }) }}</span>
        <router-link to="/orders" class="success-link">{{ t('restocking.viewInOrders') }}</router-link>
      </div>

      <div class="card budget-card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.budgetLabel') }}</h3>
        </div>
        <div class="budget-body">
          <div class="budget-display">
            <span class="budget-amount">{{ currencySymbol }}{{ Math.round(budget).toLocaleString() }}</span>
          </div>
          <div class="slider-wrapper">
            <span class="slider-label-min">{{ currencySymbol }}0</span>
            <input
              type="range"
              class="budget-slider"
              min="0"
              :max="sliderMax"
              :step="sliderStep"
              v-model.number="budget"
            />
            <span class="slider-label-max">{{ currencySymbol }}{{ sliderMax.toLocaleString() }}</span>
          </div>
          <p class="budget-help">{{ t('restocking.budgetHelp') }}</p>
        </div>
      </div>

      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.totalItems') }}</div>
          <div class="stat-value">{{ activeItemsCount }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.fullRestockCost') }}</div>
          <div class="stat-value stat-value-currency">{{ currencySymbol }}{{ Math.round(totalIdeal).toLocaleString() }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.orderTotal') }}</div>
          <div class="stat-value stat-value-currency">{{ currencySymbol }}{{ Math.round(orderTotal).toLocaleString() }}</div>
        </div>
        <div class="stat-card" :class="remainingBudget < 0 ? 'danger' : ''">
          <div class="stat-label">{{ t('restocking.remainingBudget') }}</div>
          <div class="stat-value stat-value-currency">{{ currencySymbol }}{{ Math.round(remainingBudget).toLocaleString() }}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommendations') }}</h3>
          <button
            class="btn-primary"
            :disabled="orderTotal <= 0 || submitting"
            @click="placeOrder"
          >
            {{ submitting ? t('restocking.placingOrder') : t('restocking.placeOrder') }}
          </button>
        </div>

        <div v-if="activeItemsCount === 0" class="empty-state">
          {{ t('restocking.noItems') }}
        </div>
        <div v-else class="table-container">
          <table class="restock-table">
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.itemName') }}</th>
                <th>{{ t('restocking.table.trend') }}</th>
                <th class="col-num">{{ t('restocking.table.unitCost') }}</th>
                <th class="col-num">{{ t('restocking.table.forecastQty') }}</th>
                <th class="col-num">{{ t('restocking.table.recommendedQty') }}</th>
                <th class="col-num">{{ t('restocking.table.lineCost') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in recommendations"
                :key="item.item_sku"
                :class="{ 'row-zero': item.recommendedQty === 0 }"
              >
                <td><strong>{{ item.item_sku }}</strong></td>
                <td>{{ translateProductName(item.item_name) }}</td>
                <td>
                  <span :class="['badge', item.trend]">
                    {{ t(`trends.${item.trend}`) }}
                  </span>
                </td>
                <td class="col-num">{{ currencySymbol }}{{ item.unit_cost.toLocaleString() }}</td>
                <td class="col-num">{{ item.forecasted_demand }}</td>
                <td class="col-num"><strong>{{ item.recommendedQty }}</strong></td>
                <td class="col-num">{{ currencySymbol }}{{ Math.round(item.lineCost).toLocaleString() }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency, translateProductName } = useI18n()

    const currencySymbol = computed(() => currentCurrency.value === 'JPY' ? '¥' : '$')

    const loading = ref(true)
    const error = ref(null)
    const forecasts = ref([])
    const budget = ref(0)
    const submitting = ref(false)
    const successOrder = ref(null)

    const totalIdeal = computed(() => {
      return forecasts.value.reduce((sum, f) => sum + f.forecasted_demand * f.unit_cost, 0)
    })

    const sliderMax = computed(() => Math.ceil(totalIdeal.value))

    const sliderStep = computed(() => Math.max(1, Math.round(totalIdeal.value / 200)))

    const recommendations = computed(() => {
      const scale = totalIdeal.value > 0 ? Math.min(1, budget.value / totalIdeal.value) : 0
      return forecasts.value.map(f => {
        const recommendedQty = Math.floor(f.forecasted_demand * scale)
        const lineCost = recommendedQty * f.unit_cost
        return {
          item_sku: f.item_sku,
          item_name: f.item_name,
          trend: f.trend,
          unit_cost: f.unit_cost,
          forecasted_demand: f.forecasted_demand,
          recommendedQty,
          lineCost
        }
      })
    })

    const orderTotal = computed(() => recommendations.value.reduce((sum, r) => sum + r.lineCost, 0))

    const activeItemsCount = computed(() => recommendations.value.filter(r => r.recommendedQty > 0).length)

    const remainingBudget = computed(() => budget.value - orderTotal.value)

    const loadForecasts = async () => {
      try {
        loading.value = true
        error.value = null
        const data = await api.getDemandForecasts()
        forecasts.value = data
        // Initialize budget to ~50% of totalIdeal after data loads
        budget.value = Math.round(totalIdeal.value * 0.5)
      } catch (err) {
        error.value = 'Failed to load demand forecasts: ' + err.message
        console.error(err)
      } finally {
        loading.value = false
      }
    }

    const placeOrder = async () => {
      if (orderTotal.value <= 0 || submitting.value) return
      submitting.value = true
      error.value = null
      try {
        const items = recommendations.value
          .filter(r => r.recommendedQty > 0)
          .map(r => ({
            sku: r.item_sku,
            name: r.item_name,
            quantity: r.recommendedQty,
            unit_price: r.unit_cost
          }))
        const result = await api.submitRestockOrder({
          items,
          total_value: orderTotal.value,
          budget: budget.value
        })
        successOrder.value = result
      } catch (err) {
        error.value = 'Failed to submit restock order: ' + err.message
        console.error(err)
      } finally {
        submitting.value = false
      }
    }

    onMounted(loadForecasts)

    return {
      t,
      currencySymbol,
      translateProductName,
      loading,
      error,
      budget,
      submitting,
      successOrder,
      totalIdeal,
      sliderMax,
      sliderStep,
      recommendations,
      orderTotal,
      activeItemsCount,
      remainingBudget,
      placeOrder
    }
  }
}
</script>

<style scoped>
.budget-card {
  margin-bottom: 1.5rem;
}

.budget-body {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.budget-display {
  text-align: center;
}

.budget-amount {
  font-size: 2.5rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
}

.slider-wrapper {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.slider-label-min,
.slider-label-max {
  font-size: 0.813rem;
  color: #64748b;
  font-weight: 500;
  flex-shrink: 0;
  min-width: 3rem;
}

.slider-label-max {
  text-align: right;
}

.budget-slider {
  flex: 1;
  -webkit-appearance: none;
  appearance: none;
  height: 6px;
  border-radius: 3px;
  background: #e2e8f0;
  outline: none;
  cursor: pointer;
}

.budget-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #3b82f6;
  cursor: pointer;
  border: 2px solid #fff;
  box-shadow: 0 1px 4px rgba(59, 130, 246, 0.4);
  transition: box-shadow 0.2s;
}

.budget-slider::-webkit-slider-thumb:hover {
  box-shadow: 0 1px 8px rgba(59, 130, 246, 0.6);
}

.budget-slider::-moz-range-thumb {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #3b82f6;
  cursor: pointer;
  border: 2px solid #fff;
  box-shadow: 0 1px 4px rgba(59, 130, 246, 0.4);
}

.budget-slider::-webkit-slider-runnable-track {
  background: #e2e8f0;
  border-radius: 3px;
  height: 6px;
}

.budget-slider::-moz-range-track {
  background: #e2e8f0;
  border-radius: 3px;
  height: 6px;
}

.budget-help {
  font-size: 0.813rem;
  color: #64748b;
  text-align: center;
}

.stat-value-currency {
  font-size: 1.5rem;
}

.btn-primary {
  display: inline-block;
  padding: 0.625rem 1.5rem;
  background: #2563eb;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 0.938rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-primary:hover:not(:disabled) {
  background: #1d4ed8;
}

.btn-primary:disabled {
  background: #94a3b8;
  cursor: not-allowed;
}

.success-banner {
  display: flex;
  align-items: center;
  gap: 1rem;
  background: #d1fae5;
  border: 1px solid #6ee7b7;
  color: #065f46;
  padding: 1rem 1.25rem;
  border-radius: 8px;
  margin-bottom: 1.5rem;
  font-size: 0.938rem;
  font-weight: 500;
}

.success-link {
  color: #059669;
  font-weight: 600;
  text-decoration: underline;
  white-space: nowrap;
}

.success-link:hover {
  color: #047857;
}

.empty-state {
  padding: 2rem;
  text-align: center;
  color: #64748b;
  font-size: 0.938rem;
}

.restock-table {
  width: 100%;
  border-collapse: collapse;
}

.col-num {
  text-align: right;
}

.row-zero {
  opacity: 0.45;
}
</style>
