<script lang="ts">
	const { data } = $props()
</script>
<h1>Detections</h1>
{#each data.images as image}
    {encodeURIComponent(image)}
    <img src={'/detections/' + encodeURIComponent(image)} />
{/each}