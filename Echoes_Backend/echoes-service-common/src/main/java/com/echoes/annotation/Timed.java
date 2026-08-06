package com.echoes.annotation;

import java.lang.annotation.Documented;
import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * 性能监控注解
 * 标记需要监控执行时间的方法
 *
 * @author echoes
 */
@Target({ElementType.METHOD})
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface Timed {

    /**
     * 方法描述
     */
    String description() default "";

    /**
     * 警告阈值（毫秒），超过此时间将记录警告日志
     */
    long warnThreshold() default 1000L;

    /**
     * 是否记录详细参数
     */
    boolean logParams() default false;
}
