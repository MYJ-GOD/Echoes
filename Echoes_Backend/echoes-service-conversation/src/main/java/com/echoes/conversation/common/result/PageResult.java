package com.echoes.conversation.common.result;

import java.io.Serial;
import java.io.Serializable;
import java.util.List;

/**
 * 分页结果包装类
 */
public class PageResult<T> implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    private List<T> records;
    private Long total;
    private Long page;
    private Long size;

    public PageResult() {
    }

    public PageResult(List<T> records, Long total, Long page, Long size) {
        this.records = records;
        this.total = total;
        this.page = page;
        this.size = size;
    }

    public List<T> getRecords() {
        return records;
    }

    public void setRecords(List<T> records) {
        this.records = records;
    }

    public Long getTotal() {
        return total;
    }

    public void setTotal(Long total) {
        this.total = total;
    }

    public Long getPage() {
        return page;
    }

    public void setPage(Long page) {
        this.page = page;
    }

    public Long getSize() {
        return size;
    }

    public void setSize(Long size) {
        this.size = size;
    }

    /**
     * 计算总页数
     */
    public Long getPages() {
        if (size == null || size == 0) {
            return 0L;
        }
        return (total + size - 1) / size;
    }
}

