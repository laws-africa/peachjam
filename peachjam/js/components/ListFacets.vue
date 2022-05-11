<template>
  <form
    ref="form"
    method="get"
    @change="submit"
  >
    <ul class="list-group">
      <li class="list-group-item bg-light d-flex justify-content-between align-items-center">
        <strong>Filters</strong>
        <a
          v-if="showClearAllFilter"
          href="#"
          @click.prevent="clearAll"
        >
          Clear all
        </a>
      </li>
      <li class="list-group-item" v-if="authors && authors.length">
        <div class="d-flex justify-content-between mb-2">
          <strong>Author</strong>
          <a
              v-if="author"
              href="#"
              @click.prevent="clearFacet('author')"
          >
            Clear
          </a>
        </div>
        <input name="author" :value="author"  type="hidden"/>
        <Multiselect
            name="author"
            :options="authors"
            :searchable="true"
            v-model="author"
            placeholder="Filter by author"
            :canClear="false"
        />
      </li>
      <li class="list-group-item">
        <div class="d-flex justify-content-between mb-2">
          <strong>Year</strong>
          <a
            v-if="yearParam.length"
            href="#"
            @click.prevent="clearFacet('year')"
          >
            Clear
          </a>
        </div>
        <div
          v-for="(year, index) in years"
          :key="index"
          class="d-flex justify-content-between align-items-center"
        >
          <div class="form-check">
            <input
              :id="year"
              ref="yearInput"
              class="form-check-input"
              type="checkbox"
              name="year"
              :value="year"
              :checked="yearInputChecked(year)"
            >
            <label
              class="form-check-label"
              :for="year"
            >
              {{ year }}
            </label>
          </div>
          <div
            v-if="loading"
            class="circle-loader"
          />
        </div>
      </li>
      <li class="list-group-item">
        <div class="d-flex justify-content-between mb-2">
          <strong>Alphabetical</strong>
          <div class="d-flex">
            <a
              v-if="alphabetParam.length"
              href="#"
              @click.prevent="clearFacet('alphabet')"
            >
              Clear
            </a>
            <span
              v-if="loading"
              class="circle-loader mx-2"
            />
          </div>
        </div>
        <div class="letter-radiobox-container">
          <label
            v-for="(letter, key) in alphabet"
            :key="key"
            class="letter-radiobox"
          >
            <input
              :key="key"
              ref="alphabetInput"
              :value="letter"
              :checked="alphabetInputChecked(letter)"
              type="radio"
              name="alphabet"
            >
            <span class="letter-radiobox__text">
              {{ letter }}
            </span>
          </label>
        </div>
      </li>
    </ul>
  </form>
</template>

<script>
import { nextTick} from "vue";
import Multiselect from '@vueform/multiselect'
import '@vueform/multiselect/themes/default.css'

export default {
  components: {
    Multiselect
  },
  name: 'ListFacets',
  props: ['alphabet', 'years', 'authors'],
  data: () => {
    const queryString = window.location.search;
    const urlParams = new URLSearchParams(queryString);
    const author = urlParams.get('author');
    return {
      page: 1,
      loading: false,
      author,
    }
  },

  computed: {
    alphabetParam () {
      return this.getUrlParamValue('alphabet');
    },
    yearParam () {
      return this.getUrlParamValue('year');
    },
    showClearAllFilter () {
      return this.alphabetParam.length || this.yearParam.length;
    }
  },
  methods: {
    yearInputChecked (value) {
      return this.yearParam.includes(value);
    },
    alphabetInputChecked (value) {
      return this.alphabetParam.includes(value);
    },

    clearAll () {
      window.location.href = `${window.location.origin}${window.location.pathname}`;
    },

    clearFacet (key) {
      const queryString = window.location.search;
      const urlParams = new URLSearchParams(queryString);
      urlParams.delete(key);
      window.location.href = `${window.location.origin}${window.location.pathname}?${urlParams.toString()}`;
    },
    getUrlParamValue (key) {
      const queryString = window.location.search;
      const urlParams = new URLSearchParams(queryString);
      return urlParams.getAll(key);
    },
    submit () {
      this.loading = true;
      //On submit page refreshes
      this.$refs.form.submit();
    },
  },
  watch: {
    author() {
      nextTick().then(() => {
        this.submit();
      })
    }
  }
};
</script>

<style scoped>
.letter-radiobox-container {
  display: flex;
  flex-flow: row wrap;
  justify-content: center;
}

.letter-radiobox {
  height: 40px;
  width: 40px;
  border-radius: 5px;
  cursor: pointer;
  overflow: hidden;
}
.letter-radiobox input {
  display: none;
}

.letter-radiobox__text {
  height: 100%;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 200ms ease-in-out, background-color 200ms ease-in-out;
  text-transform: uppercase;
}

.letter-radiobox:hover .letter-radiobox__text {
  background-color: rgba(238, 120, 69, 0.3);
}

.letter-radiobox input:checked + .letter-radiobox__text {
  background-color: #EE7845;
  color: white;
}

</style>
