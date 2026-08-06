package com.echoes.gateway.test;

import com.echoes.gateway.common.util.AliOssUtil;
import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.Test;

public class AliOssTest {
    @Test
    public void testAliOss() {
        String endpoint = System.getenv("OSS_ENDPOINT");
        String accessKeyId = System.getenv("OSS_ACCESS_KEY_ID");
        String accessKeySecret = System.getenv("OSS_ACCESS_KEY_SECRET");
        String bucketName = System.getenv("OSS_BUCKET");
        String testFile = System.getenv("OSS_TEST_FILE");

        Assumptions.assumeTrue(
                endpoint != null && !endpoint.isBlank()
                        && accessKeyId != null && !accessKeyId.isBlank()
                        && accessKeySecret != null && !accessKeySecret.isBlank()
                        && bucketName != null && !bucketName.isBlank()
                        && testFile != null && !testFile.isBlank(),
                "OSS test skipped: missing environment variables"
        );

        AliOssUtil aliOssUtil = AliOssUtil.builder()
                .endpoint(endpoint)
                .accessKeyId(accessKeyId)
                .accessKeySecret(accessKeySecret)
                .bucketName(bucketName)
                .build();
        aliOssUtil.upload("test-content".getBytes(), testFile);
    }
}
