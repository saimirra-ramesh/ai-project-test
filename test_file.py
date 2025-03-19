def test_rebalance_in_during_index_building(self):
        RestConnection(self.master).modify_memory_quota(kv_quota=800,fts_quota=2000)
        if self._input.param("must_fail", False):
            self.fail("Temporal fail to let all the other tests to be passed")
        self.load_data()
        self.create_fts_indexes_all_buckets()
        self.sleep(10)
        self.log.info("Index building has begun...")
        for index in self._cb_cluster.get_indexes():
            self.log.info("Index count for %s: %s"
                          %(index.name, index.get_indexed_doc_count()))
        self._cb_cluster.rebalance_in(num_nodes=1, services=["kv,fts"])
        for index in self._cb_cluster.get_indexes():
            self.is_index_partitioned_balanced(index)
        self.wait_for_indexing_complete()
        self.validate_index_count(equal_bucket_doc_count=True)
        frest = RestConnection(self._cb_cluster.get_fts_nodes()[0])
        err = self.validate_partition_distribution(frest)
        if len(err) > 0:
            self.fail(err)

def test_rebalance_out_during_index_building(self):
        RestConnection(self.master).modify_memory_quota(fts_quota=2400)
        self.load_data()
        self.create_fts_indexes_all_buckets()
        self.sleep(30)
        self.log.info("Index building has begun...")
        for index in self._cb_cluster.get_indexes():
            self.log.info("Index count for %s: %s"
                          %(index.name, index.get_indexed_doc_count()))
        self._cb_cluster.rebalance_out()
        for index in self._cb_cluster.get_indexes():
            self.is_index_partitioned_balanced(index)
        self.wait_for_indexing_complete()
        self.validate_index_count(equal_bucket_doc_count=True)
        frest = RestConnection(self._cb_cluster.get_fts_nodes()[0])
        err = self.validate_partition_distribution(frest)
        if len(err) > 0:
            self.fail(err)

def test_eventing_swap_rebalance_when_existing_eventing_node_is_processing_mutations(self):
        self.create_save_handlers()
        self.deploy_all_handlers()
        # load data
        self.load_data_to_collection(self.docs_per_day * self.num_docs, "src_bucket._default._default",wait_for_loading=False)
        self.load_data_to_collection(self.docs_per_day * self.num_docs, "src_bucket.scope_1.coll_1",wait_for_loading=False)
        # swap rebalance an eventing node when eventing is processing mutations
        services_in = ["eventing"]
        nodes_out_ev = self.get_nodes_from_services_map(service_type="eventing", get_all_nodes=True)
        rebalance = self.cluster.async_rebalance(self.servers[:self.nodes_init], [self.servers[self.nodes_init]],
                                                 nodes_out_ev, services=services_in)
        reached = RestHelper(self.rest).rebalance_reached(retry_count=150)
        self.assertTrue(reached, "rebalance failed, stuck or did not complete")
        rebalance.result()
        # Wait for eventing to catch up with all the update mutations and verify results after rebalance
        self.verify_all_handler(self.docs_per_day * self.num_docs)
        self.verify_doc_count_collections("src_bucket.scope_1.coll_1", self.docs_per_day * self.num_docs * 2)
        # delete json documents
        self.load_data_to_collection(self.docs_per_day * self.num_docs, "src_bucket._default._default",is_delete=True)
        self.load_data_to_collection(self.docs_per_day * self.num_docs, "src_bucket.scope_1.coll_1",is_delete=True)
        # Wait for eventing to catch up with all the delete mutations and verify results
        self.verify_all_handler(0)
        self.verify_doc_count_collections("src_bucket.scope_1.coll_1", self.docs_per_day * self.num_docs)
        self.undeploy_delete_all_functions()
        # Get all eventing nodes
        nodes_out_list = self.get_nodes_from_services_map(service_type="eventing", get_all_nodes=True)
        # Fail over all eventing nodes and rebalance them out
        self.cluster.failover([self.master], failover_nodes=nodes_out_list, graceful=False)
        rebalance = self.cluster.async_rebalance(self.servers[:self.nodes_init + 1], [], nodes_out_list)
        reached = RestHelper(self.rest).rebalance_reached(retry_count=150)
        self.assertTrue(reached, "rebalance failed, stuck or did not complete")
        rebalance.result()

   