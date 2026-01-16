<script lang="ts">
	const { data } = $props()
</script>
{#if data.images.length === 0}
    <p>No detections found</p>
{:else}
    {#each data.images as image}
        {encodeURIComponent(image)}
        <img src={'/detections/' + encodeURIComponent(image)} />
    {/each}
{/if}