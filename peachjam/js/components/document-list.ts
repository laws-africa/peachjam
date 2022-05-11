import ListFacets from './ListFacets.vue';
import { createApp } from 'vue';

class DocumentList {
  constructor (root: HTMLElement) {
    const facetsElement:any = root.querySelector('#list-facets');

    const alphabet = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z'];
    const years = ['2022', '2021', '2020', '2019', '2018', '2017', '2016', '2015', '2014', '2013', '2012', '2011'];
    const authorsJsonElement = root.querySelector("#authors");
    let authors = [];
    if(authorsJsonElement && authorsJsonElement.textContent != null) {
      authors = JSON.parse(authorsJsonElement.textContent);
    }
    createApp(ListFacets, {
      alphabet,
      years,
      authors
    }).mount(facetsElement);
  }
}

export default DocumentList;
