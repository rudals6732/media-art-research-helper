package com.project.controller;

import com.project.model.Paper;
import java.util.List;

public class ReportRequest {
    private String topic;
    private List<Paper> papers;

    public ReportRequest() {}

    public String getTopic() { return topic; }
    public void setTopic(String topic) { this.topic = topic; }

    public List<Paper> getPapers() { return papers; }
    public void setPapers(List<Paper> papers) { this.papers = papers; }
}
