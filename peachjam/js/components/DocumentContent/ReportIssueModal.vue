Vue.component("modal",{
	props:['name'],
	template:`
		<div class="modal fade in modal-active">
			<div class="modal-dialog">
					<div class="modal-content">
						<div class="modal-header">
							<button type="button" @click="$emit('close')" class="close"><span >&times;</span></button>
							<h4 class="modal-title">
								{{name}}
							</h4>
						</div>
						<div class="modal-body">
								<slot></slot>
						</div>
						<div class="modal-footer">
							<button type="button" class="btn btn-default" @click="$emit('close')">Close</button>
							<button type="button" class="btn btn-primary">Save changes</button>
						</div>
				</div>
			</div>
		</div>`
})

new Vue({
	el:"#root",
	data:{
		showModal:false
	}
});
